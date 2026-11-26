"""Programmatic data retrieval with retries, client-side rate limiting and on-disk caching.

Sources
-------
* Prices : Tiingo daily endpoint (adjusted OHLCV).            -> raw/prices_{TICKER}_{start}_{end}.csv
* News   : Finnhub company-news, fetched in monthly chunks.    -> raw/news_finnhub_{TICKER}_{from}_{to}.csv
* News   : NewsAPI /v2/everything (optional, ~1 month only).    -> raw/news_newsapi_{TICKER}_{from}_{to}.csv

Every raw response is written to CSV *unchanged in content* (only flattened) so that
``--offline`` reruns reproduce the analysis without network access. Retrieval timestamps
are recorded in ``raw/retrieval_log.json`` and surface in the data cards.

Nothing here ever invents data: if a request fails after retries the ticker/chunk is
reported as missing and the pipeline continues with what it has (or stops if nothing).
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
import pandas as pd

from analysis import config as C

log = logging.getLogger(__name__)


class MissingKeysError(RuntimeError):
    """Raised when required API keys are absent (pipeline exits with code 2)."""


class NoCachedDataError(RuntimeError):
    """Raised in --offline mode when no cached raw CSVs exist."""


class CollectionError(RuntimeError):
    """Raised when a request still fails after all retries."""


class RateLimiter:
    """Minimum-interval limiter: at most ``per_minute`` calls per rolling minute (approx.)."""

    def __init__(self, per_minute: float):
        self.min_interval = 60.0 / per_minute if per_minute > 0 else 0.0
        self._last = 0.0

    def wait(self) -> None:
        now = time.monotonic()
        delay = self._last + self.min_interval - now
        if delay > 0:
            time.sleep(delay)
        self._last = time.monotonic()


# Tiingo free: 50 req/hour -> ~0.83/min; we stay just under. Finnhub free: 60/min -> 55.
TIINGO_LIMITER = RateLimiter(per_minute=0.8)
FINNHUB_LIMITER = RateLimiter(per_minute=55)
NEWSAPI_LIMITER = RateLimiter(per_minute=30)


def get_json(client: httpx.Client, url: str, *, params: dict | None = None, headers: dict | None = None,
             limiter: RateLimiter | None = None, retries: int = 4, backoff: float = 2.0) -> Any:
    """GET with retries on network errors, HTTP 429 and 5xx (exponential backoff)."""
    last_err: Exception | None = None
    for attempt in range(retries):
        if limiter:
            limiter.wait()
        try:
            r = client.get(url, params=params, headers=headers, timeout=30.0)
            if r.status_code == 429 or r.status_code >= 500:
                retry_after = float(r.headers.get("Retry-After", 0) or 0)
                wait = max(retry_after, backoff ** attempt)
                log.warning("HTTP %s from %s; retrying in %.1fs", r.status_code, url, wait)
                last_err = CollectionError(f"HTTP {r.status_code}")
                time.sleep(wait)
                continue
            if r.status_code in (401, 403):
                raise CollectionError(f"HTTP {r.status_code} from {url}: check that the API key is valid.")
            r.raise_for_status()
            return r.json()
        except (httpx.TransportError, httpx.TimeoutException) as exc:
            last_err = exc
            wait = backoff ** attempt
            log.warning("Network error %r for %s; retrying in %.1fs", exc, url, wait)
            time.sleep(wait)
    raise CollectionError(f"Request to {url} failed after {retries} attempts: {last_err}")


# ---------------------------------------------------------------------------
# retrieval log
# ---------------------------------------------------------------------------

def _log_path(raw_dir: Path) -> Path:
    return raw_dir / "retrieval_log.json"


def load_retrieval_log(raw_dir: Path) -> dict:
    p = _log_path(raw_dir)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def record_retrieval(raw_dir: Path, filename: str, source: str, url: str) -> None:
    data = load_retrieval_log(raw_dir)
    data[filename] = {"source": source, "url": url,
                      "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    _log_path(raw_dir).write_text(json.dumps(data, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# prices
# ---------------------------------------------------------------------------

def _latest_cache(raw_dir: Path, pattern: str) -> Path | None:
    files = sorted(raw_dir.glob(pattern), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def fetch_prices(ticker: str, start: date, end: date, api_key: str, raw_dir: Path, *,
                 offline: bool = False, client: httpx.Client | None = None) -> pd.DataFrame | None:
    """Return raw Tiingo rows for one ticker (cached). ``None`` if unavailable."""
    path = raw_dir / f"prices_{ticker}_{start.isoformat()}_{end.isoformat()}.csv"
    if path.exists():
        log.info("prices %s: using cache %s", ticker, path.name)
        return pd.read_csv(path)
    if offline:
        alt = _latest_cache(raw_dir, f"prices_{ticker}_*.csv")
        if alt is None:
            log.warning("prices %s: no cached CSV (offline)", ticker)
            return None
        log.info("prices %s: offline, using closest cache %s", ticker, alt.name)
        return pd.read_csv(alt)
    url = C.TIINGO_URL.format(ticker=ticker)
    own = client is None
    client = client or httpx.Client()
    try:
        data = get_json(client, url, params={"startDate": start.isoformat(), "endDate": end.isoformat(),
                                             "format": "json"},
                        headers={"Authorization": f"Token {api_key}", "Content-Type": "application/json"},
                        limiter=TIINGO_LIMITER)
    except CollectionError as exc:
        log.error("prices %s: %s", ticker, exc)
        return None
    finally:
        if own:
            client.close()
    if not isinstance(data, list) or not data:
        log.warning("prices %s: empty response", ticker)
        return None
    df = pd.DataFrame(data)
    df.insert(0, "ticker", ticker)
    df.to_csv(path, index=False)
    record_retrieval(raw_dir, path.name, "Tiingo daily prices", url)
    return df


# ---------------------------------------------------------------------------
# news
# ---------------------------------------------------------------------------

def month_chunks(start: date, end: date) -> list[tuple[date, date]]:
    """Split [start, end] into calendar-month chunks (Finnhub caps results per call)."""
    chunks = []
    cur = start
    while cur <= end:
        nxt = (cur.replace(day=1) + timedelta(days=32)).replace(day=1)
        chunk_end = min(nxt - timedelta(days=1), end)
        chunks.append((cur, chunk_end))
        cur = chunk_end + timedelta(days=1)
    return chunks


NEWS_COLUMNS = ["ticker", "source_api", "id", "datetime", "headline", "summary", "source", "url", "category", "related"]


def fetch_finnhub_news(ticker: str, start: date, end: date, api_key: str, raw_dir: Path, *,
                       offline: bool = False, client: httpx.Client | None = None) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    today = date.today()
    own = client is None and not offline
    if own:
        client = httpx.Client()
    try:
        for a, b in month_chunks(start, end):
            path = raw_dir / f"news_finnhub_{ticker}_{a.isoformat()}_{b.isoformat()}.csv"
            # A chunk that ended before today is immutable -> safe to reuse. Current chunk refetched online.
            if path.exists() and (offline or b < today):
                frames.append(pd.read_csv(path, dtype={"id": str}))
                continue
            if offline:
                continue
            try:
                data = get_json(client, C.FINNHUB_NEWS_URL,
                                params={"symbol": ticker, "from": a.isoformat(), "to": b.isoformat()},
                                headers={"X-Finnhub-Token": api_key}, limiter=FINNHUB_LIMITER)
            except CollectionError as exc:
                log.error("news %s %s..%s: %s", ticker, a, b, exc)
                continue
            df = pd.DataFrame(data if isinstance(data, list) else [])
            df.insert(0, "ticker", ticker)
            df.insert(1, "source_api", "finnhub")
            for col in NEWS_COLUMNS:
                if col not in df.columns:
                    df[col] = pd.NA
            df = df[NEWS_COLUMNS]
            df.to_csv(path, index=False)
            record_retrieval(raw_dir, path.name, "Finnhub company-news", C.FINNHUB_NEWS_URL)
            frames.append(df)
    finally:
        if own and client is not None:
            client.close()
    if not frames:
        return pd.DataFrame(columns=NEWS_COLUMNS)
    return pd.concat([f for f in frames if not f.empty] or [frames[0]], ignore_index=True)


def fetch_newsapi_news(ticker: str, api_key: str, raw_dir: Path, *, offline: bool = False,
                       end: date | None = None, client: httpx.Client | None = None) -> pd.DataFrame:
    """Optional supplement: NewsAPI developer plan only covers ~1 month back."""
    end = end or date.today()
    start = end - timedelta(days=29)
    path = raw_dir / f"news_newsapi_{ticker}_{start.isoformat()}_{end.isoformat()}.csv"
    if path.exists():
        return pd.read_csv(path, dtype={"id": str})
    if offline:
        alt = _latest_cache(raw_dir, f"news_newsapi_{ticker}_*.csv")
        return pd.read_csv(alt, dtype={"id": str}) if alt else pd.DataFrame(columns=NEWS_COLUMNS)
    query = f'"{C.COMPANY_NAMES.get(ticker, ticker)}"'
    own = client is None
    client = client or httpx.Client()
    try:
        data = get_json(client, C.NEWSAPI_URL,
                        params={"q": query, "from": start.isoformat(), "to": end.isoformat(), "language": "en",
                                "sortBy": "publishedAt", "pageSize": 100},
                        headers={"X-Api-Key": api_key}, limiter=NEWSAPI_LIMITER)
    except CollectionError as exc:
        log.warning("newsapi %s: %s (optional source, continuing)", ticker, exc)
        return pd.DataFrame(columns=NEWS_COLUMNS)
    finally:
        if own:
            client.close()
    rows = []
    for art in (data or {}).get("articles", []):
        url = art.get("url") or ""
        published = pd.to_datetime(art.get("publishedAt"), utc=True, errors="coerce")
        rows.append({
            "ticker": ticker, "source_api": "newsapi",
            # NewsAPI has no article id -> stable hash of the URL.
            "id": "na_" + hashlib.sha1(url.encode("utf-8")).hexdigest()[:16],
            "datetime": int(published.timestamp()) if pd.notna(published) else pd.NA,
            "headline": art.get("title"), "summary": art.get("description"),
            "source": (art.get("source") or {}).get("name"), "url": url, "category": "newsapi", "related": ticker,
        })
    df = pd.DataFrame(rows, columns=NEWS_COLUMNS)
    df.to_csv(path, index=False)
    record_retrieval(raw_dir, path.name, "NewsAPI everything", C.NEWSAPI_URL)
    return df


def collect_all(cfg: C.PipelineConfig, keys: dict[str, str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Collect prices and news for all tickers. Returns (raw_prices, raw_news)."""
    raw = cfg.raw_dir
    price_frames, news_frames = [], []
    client = None if cfg.offline else httpx.Client()
    try:
        for t in cfg.tickers:
            p = fetch_prices(t, cfg.price_start, cfg.news_end, keys.get("tiingo", ""), raw,
                             offline=cfg.offline, client=client)
            if p is not None and not p.empty:
                price_frames.append(p)
            n = fetch_finnhub_news(t, cfg.news_start, cfg.news_end, keys.get("finnhub", ""), raw,
                                   offline=cfg.offline, client=client)
            if not n.empty:
                news_frames.append(n)
            if cfg.use_newsapi and (keys.get("newsapi") or cfg.offline):
                na = fetch_newsapi_news(t, keys.get("newsapi", ""), raw, offline=cfg.offline,
                                        end=cfg.news_end, client=client)
                if not na.empty:
                    news_frames.append(na)
    finally:
        if client is not None:
            client.close()
    if not price_frames:
        if cfg.offline:
            raise NoCachedDataError(
                f"No cached price CSVs found in {raw}. Run once online (with API keys) before using --offline.")
        raise CollectionError("No price data could be downloaded for any ticker (see log above).")
    prices = pd.concat(price_frames, ignore_index=True)
    news = pd.concat(news_frames, ignore_index=True) if news_frames else pd.DataFrame(columns=NEWS_COLUMNS)
    return prices, news
