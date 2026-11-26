"""Shared outbound HTTP helper that maps provider failures to typed errors."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from .errors import PlanRestricted, ProviderError, RateLimited
from .rate_limit import RateLimiter

log = logging.getLogger("stocksage.http")

_client: httpx.AsyncClient | None = None


def client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=8.0), headers={"User-Agent": "StockSage/1.0"})
    return _client


async def close_client() -> None:
    if _client is not None and not _client.is_closed:
        await _client.aclose()


# Connection-level failures (dropped keep-alive sockets, DNS hiccups, resets after
# the machine wakes from sleep) are usually gone on the next attempt, so retry them
# briefly. Read timeouts are not retried: the provider is slow, and retrying would
# only multiply the wait.
_RETRY_DELAYS = (0.25, 1.0)
_RETRYABLE = (httpx.ConnectError, httpx.ConnectTimeout, httpx.RemoteProtocolError, httpx.ReadError, httpx.WriteError)


async def _send_with_retry(
    provider: str, method: str, url: str, *, params, headers, json_body, timeout,
) -> httpx.Response:
    attempts = len(_RETRY_DELAYS) + 1
    for attempt in range(1, attempts + 1):
        try:
            return await client().request(
                method, url, params=params, headers=headers, json=json_body,
                timeout=timeout if timeout else httpx.USE_CLIENT_DEFAULT,
            )
        except _RETRYABLE as exc:
            if attempt < attempts:
                log.info("%s connection error (%s), retry %d/%d", provider, type(exc).__name__, attempt, attempts - 1)
                await asyncio.sleep(_RETRY_DELAYS[attempt - 1])
                continue
            log.warning("%s could not be reached after %d attempts: %s: %s", provider, attempts, type(exc).__name__, exc)
            raise ProviderError(f"{provider} could not be reached", details={"transient": True}) from exc
        except httpx.TimeoutException as exc:
            raise ProviderError(f"{provider} timed out", details={"transient": True}) from exc
        except httpx.HTTPError as exc:
            log.warning("%s request failed: %s: %s", provider, type(exc).__name__, exc)
            raise ProviderError(f"{provider} could not be reached", details={"transient": True}) from exc
    raise AssertionError("unreachable")


async def get_json(
    provider: str,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    limiter: RateLimiter | None = None,
    method: str = "GET",
    json_body: Any = None,
    timeout: float | None = None,
) -> Any:
    if limiter and not await limiter.acquire():
        raise RateLimited(f"{provider} request budget exhausted; try again shortly")
    resp = await _send_with_retry(
        provider, method, url, params=params, headers=headers, json_body=json_body, timeout=timeout,
    )

    # Never log query params: they may contain API keys.
    log.debug("%s %s -> %s", provider, url.split("?")[0], resp.status_code)
    if resp.status_code == 429:
        raise RateLimited(f"{provider} rate limit reached", details={"status": 429, "transient": True})
    if resp.status_code in (401,):
        raise ProviderError(f"{provider} rejected the API key", code="invalid_api_key")
    if resp.status_code == 403:
        raise PlanRestricted(f"{provider} plan does not include this data")
    if resp.status_code >= 400:
        snippet = resp.text[:200].replace("\n", " ")
        raise ProviderError(
            f"{provider} returned HTTP {resp.status_code}",
            details={"status": resp.status_code, "transient": resp.status_code >= 500, "body": snippet},
        )
    try:
        return resp.json()
    except ValueError as exc:
        raise ProviderError(f"{provider} returned an unreadable response") from exc
