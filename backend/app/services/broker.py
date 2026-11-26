"""Alpaca brokerage integration — PAPER environment only.

Orders placed here go to Alpaca's paper-trading environment: a real broker's order
system with simulated fills and virtual money. The base URL is hard-coded to the
paper endpoint and is NOT configurable, so this code cannot place real-money trades.

API reference: https://docs.alpaca.markets/reference (Trading API v2).
Auth headers: APCA-API-KEY-ID / APCA-API-SECRET-KEY.
"""
from __future__ import annotations

from typing import Any

import httpx

from ..config import get_settings
from ..core import http
from ..core.errors import AppError, ProviderError, ProviderNotConfigured, RateLimited
from ..core.rate_limit import RateLimiter

PAPER_BASE_URL = "https://paper-api.alpaca.markets"  # deliberately constant; never the live API
_limiter = RateLimiter(150, 60.0, max_wait=5.0)  # Alpaca allows 200 req/min; keep headroom


def configured() -> bool:
    s = get_settings()
    return bool(s.alpaca_api_key_id and s.alpaca_api_secret_key)


def _headers() -> dict[str, str]:
    s = get_settings()
    if not configured():
        raise ProviderNotConfigured(
            "Alpaca paper trading is not configured. Add ALPACA_API_KEY_ID and ALPACA_API_SECRET_KEY "
            "(from a Paper account) to backend/.env and restart the backend."
        )
    return {"APCA-API-KEY-ID": s.alpaca_api_key_id, "APCA-API-SECRET-KEY": s.alpaca_api_secret_key}


async def _call(method: str, path: str, *, params: dict | None = None, body: Any = None) -> Any:
    headers = _headers()
    if not await _limiter.acquire():
        raise RateLimited("Alpaca request budget exhausted; try again shortly")
    try:
        resp = await http.client().request(method, f"{PAPER_BASE_URL}{path}", params=params, json=body,
                                           headers=headers, timeout=20.0)
    except httpx.TimeoutException as exc:
        raise ProviderError("Alpaca timed out", details={"transient": True}) from exc
    except httpx.HTTPError as exc:
        raise ProviderError("Alpaca could not be reached", details={"transient": True}) from exc
    if resp.status_code == 401 or (resp.status_code == 403 and method == "GET"):
        # Alpaca answers 401/403 on reads when the keys are wrong (e.g. live keys used against paper).
        raise ProviderError("Alpaca rejected the API keys. Use keys generated for your Paper account.", code="invalid_api_key")
    if resp.status_code == 429:
        raise RateLimited("Alpaca rate limit reached")
    if resp.status_code >= 400:
        # Alpaca explains order rejections (e.g. insufficient buying power, 403/422) in "message".
        try:
            msg = (resp.json() or {}).get("message")
        except ValueError:
            msg = None
        code = "order_rejected" if resp.status_code in (403, 422) else "provider_error"
        status = 422 if code == "order_rejected" else (404 if resp.status_code == 404 else 502)
        raise AppError(f"Alpaca: {msg or f'HTTP {resp.status_code}'}", code=code, status_code=status)
    if resp.status_code == 204 or not resp.content:
        return None
    try:
        return resp.json()
    except ValueError as exc:
        raise ProviderError("Alpaca returned an unreadable response") from exc


def _f(x: Any) -> float | None:
    try:
        return float(x) if x is not None and x != "" else None
    except (TypeError, ValueError):
        return None


async def account() -> dict:
    a = await _call("GET", "/v2/account")
    return {
        "account_number": a.get("account_number"),
        "status": a.get("status"),
        "currency": a.get("currency"),
        "cash": _f(a.get("cash")),
        "equity": _f(a.get("equity")),
        "last_equity": _f(a.get("last_equity")),
        "buying_power": _f(a.get("buying_power")),
        "portfolio_value": _f(a.get("portfolio_value")),
        "long_market_value": _f(a.get("long_market_value")),
        "trading_blocked": bool(a.get("trading_blocked")),
        "pattern_day_trader": bool(a.get("pattern_day_trader")),
        "environment": "paper",
    }


async def positions() -> list[dict]:
    rows = await _call("GET", "/v2/positions")
    return [{
        "symbol": p.get("symbol"),
        "qty": _f(p.get("qty")),
        "side": p.get("side"),
        "avg_entry_price": _f(p.get("avg_entry_price")),
        "current_price": _f(p.get("current_price")),
        "market_value": _f(p.get("market_value")),
        "cost_basis": _f(p.get("cost_basis")),
        "unrealized_pl": _f(p.get("unrealized_pl")),
        "unrealized_plpc": (_f(p.get("unrealized_plpc")) or 0) * 100 if p.get("unrealized_plpc") is not None else None,
        "change_today_pct": (_f(p.get("change_today")) or 0) * 100 if p.get("change_today") is not None else None,
    } for p in rows or []]


def _order(o: dict) -> dict:
    return {
        "id": o.get("id"),
        "symbol": o.get("symbol"),
        "side": o.get("side"),
        "type": o.get("type") or o.get("order_type"),
        "qty": _f(o.get("qty")),
        "filled_qty": _f(o.get("filled_qty")),
        "filled_avg_price": _f(o.get("filled_avg_price")),
        "limit_price": _f(o.get("limit_price")),
        "time_in_force": o.get("time_in_force"),
        "status": o.get("status"),
        "submitted_at": o.get("submitted_at"),
        "filled_at": o.get("filled_at"),
        "canceled_at": o.get("canceled_at"),
    }


async def orders(status: str = "all", limit: int = 50) -> list[dict]:
    rows = await _call("GET", "/v2/orders", params={"status": status, "limit": limit, "direction": "desc"})
    return [_order(o) for o in rows or []]


async def place_order(symbol: str, side: str, qty: int, order_type: str, limit_price: float | None) -> dict:
    body: dict[str, Any] = {"symbol": symbol, "qty": str(qty), "side": side, "type": order_type, "time_in_force": "day"}
    if order_type == "limit":
        if not limit_price or limit_price <= 0:
            raise AppError("A limit order needs a positive limit price.", code="invalid_limit_price", status_code=422)
        body["limit_price"] = f"{limit_price:.2f}"
    return _order(await _call("POST", "/v2/orders", body=body))


async def cancel_order(order_id: str) -> None:
    await _call("DELETE", f"/v2/orders/{order_id}")


async def clock() -> dict:
    c = await _call("GET", "/v2/clock")
    return {"is_open": c.get("is_open"), "next_open": c.get("next_open"), "next_close": c.get("next_close"), "timestamp": c.get("timestamp")}
