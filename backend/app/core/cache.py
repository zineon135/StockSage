"""Two-tier cache.

* Tier 1: in-memory TTL cache to respect provider rate limits.
* Tier 2: SQLite "last known good" store. When a provider fails, the last good
  payload is returned with ``stale=True`` and its ORIGINAL timestamp, so the UI
  can show a visible stale-data warning. Old data is never silently presented
  as current.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from ..database import SessionLocal
from ..models import CacheEntry
from .errors import AppError, ProviderError

log = logging.getLogger("stocksage.cache")


@dataclass
class Envelope:
    data: Any
    source: str
    fetched_at: datetime
    stale: bool = False
    stale_reason: str | None = None

    def meta(self) -> dict:
        return {
            "source": self.source,
            "fetched_at": self.fetched_at.isoformat(),
            "stale": self.stale,
            "stale_reason": self.stale_reason,
        }


_mem: dict[str, tuple[float, Envelope]] = {}
_locks: dict[str, asyncio.Lock] = {}


def _lock(key: str) -> asyncio.Lock:
    if key not in _locks:
        _locks[key] = asyncio.Lock()
    return _locks[key]


def _persist(key: str, env: Envelope) -> None:
    try:
        with SessionLocal() as db:
            row = db.get(CacheEntry, key)
            payload = json.dumps(env.data, default=str)
            if row:
                row.payload, row.source, row.fetched_at = payload, env.source, env.fetched_at
            else:
                db.add(CacheEntry(key=key, payload=payload, source=env.source, fetched_at=env.fetched_at))
            db.commit()
    except Exception:  # pragma: no cover - cache persistence must never break a request
        log.exception("Failed to persist cache entry %s", key)


def _load_persisted(key: str) -> Envelope | None:
    try:
        with SessionLocal() as db:
            row = db.get(CacheEntry, key)
            if not row:
                return None
            fetched = row.fetched_at if row.fetched_at.tzinfo else row.fetched_at.replace(tzinfo=timezone.utc)
            return Envelope(data=json.loads(row.payload), source=row.source, fetched_at=fetched)
    except Exception:  # pragma: no cover
        log.exception("Failed to load cache entry %s", key)
        return None


async def cached(
    key: str,
    ttl_seconds: float,
    source: str,
    fetcher: Callable[[], Awaitable[Any]],
    *,
    persist: bool = True,
) -> Envelope:
    """Return fresh data from cache or fetcher; fall back to last-known-good on provider failure."""
    now = time.monotonic()
    hit = _mem.get(key)
    if hit and hit[0] > now:
        return hit[1]

    async with _lock(key):
        hit = _mem.get(key)
        if hit and hit[0] > time.monotonic():
            return hit[1]
        if persist and not hit:
            # Survive restarts without re-spending provider quota.
            saved = _load_persisted(key)
            if saved:
                age = (datetime.now(timezone.utc) - saved.fetched_at).total_seconds()
                if age < ttl_seconds:
                    _mem[key] = (time.monotonic() + (ttl_seconds - age), saved)
                    return saved
        try:
            data = await fetcher()
        except ProviderError as exc:
            fallback = hit[1] if hit else (_load_persisted(key) if persist else None)
            if fallback is None:
                raise
            log.warning("Serving stale data for %s: %s", key, exc.message)
            stale = Envelope(
                data=fallback.data,
                source=fallback.source,
                fetched_at=fallback.fetched_at,
                stale=True,
                stale_reason=f"{source} is currently unavailable ({exc.message}). Showing the last successfully "
                f"retrieved data from {fallback.fetched_at.strftime('%Y-%m-%d %H:%M UTC')}.",
            )
            # Short memo so we don't hammer a failing provider.
            _mem[key] = (time.monotonic() + min(ttl_seconds, 30), stale)
            return stale
        except AppError:
            raise
        env = Envelope(data=data, source=source, fetched_at=datetime.now(timezone.utc))
        _mem[key] = (time.monotonic() + ttl_seconds, env)
        if persist:
            _persist(key, env)
        return env


def clear_memory_cache() -> None:
    _mem.clear()
