from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query

from ..core.errors import AppError
from ..services import analytics, market_data as md
from .common import section

router = APIRouter(prefix="/api/stocks", tags=["stocks"])

RangeKey = Literal["1W", "1M", "3M", "6M", "1Y", "5Y"]


@router.get("/search")
async def search(q: str = Query(..., min_length=1, max_length=40)):
    env = await md.search(q)
    return {"data": env.data, "meta": env.meta()}


@router.get("/{symbol}")
async def detail(symbol: str):
    symbol = md.normalize_symbol(symbol)
    import asyncio

    quote, profile, metrics = await asyncio.gather(
        section(md.get_quote(symbol)), section(md.get_profile(symbol)), section(md.get_metrics(symbol))
    )
    if "error" in quote and "error" in profile and quote["error"]["code"] == "not_found":
        raise AppError(f"We couldn't find data for '{symbol}'.", code="not_found", status_code=404)
    return {"symbol": symbol, "quote": quote, "profile": profile, "metrics": metrics}


@router.get("/{symbol}/history")
async def history(symbol: str, range_key: RangeKey = Query("1Y", alias="range")):
    env = await md.get_daily_history(symbol)
    bars = env.data["bars"]
    closes = [b["close"] for b in bars]
    sma50 = analytics.sma(closes, 50)
    sma200 = analytics.sma(closes, 200)
    start_idx = len(bars) - len(md.slice_range(bars, range_key))
    out = []
    for i in range(start_idx, len(bars)):
        b = bars[i]
        out.append({**b, "sma50": sma50[i], "sma200": sma200[i]})
    first, last = (out[0]["close"], out[-1]["close"]) if out else (None, None)
    earliest = bars[0]["date"] if bars else None
    available_ranges = [k for k, d in md.RANGE_DAYS.items() if bars and len(bars) >= min(d * 0.6, 4)]
    return {
        "symbol": env.data["symbol"],
        "range": range_key,
        "bars": out,
        "performance_pct": analytics.pct_change(first, last) if out else None,
        "provider": env.data.get("provider"),
        "adjusted": env.data.get("adjusted"),
        "earliest_available": earliest,
        "available_ranges": available_ranges,
        "note": "Daily end-of-day prices" + (" adjusted for splits and dividends" if env.data.get("adjusted") else "")
                + ". Today's session appears after the provider publishes end-of-day data.",
        "meta": env.meta(),
    }


@router.get("/{symbol}/intraday")
async def intraday(symbol: str):
    env = await md.get_intraday(symbol)
    return {"data": env.data, "meta": env.meta()}


@router.get("/{symbol}/technicals")
async def technicals(symbol: str):
    env = await md.get_daily_history(symbol)
    bars = env.data["bars"]
    if len(bars) < 15:
        raise AppError("Not enough price history to compute indicators.", code="insufficient_history")
    dates = [b["date"] for b in bars]
    closes = [b["close"] for b in bars]
    vols = [b["volume"] for b in bars]
    s = analytics.technical_summary(dates, closes, vols)
    series = s.pop("series")
    rv = analytics.rolling_volatility(closes, 30)
    n = min(len(bars), 252)
    chart = [
        {"date": dates[i], "close": closes[i], "rsi14": series["rsi14"][i], "volume": vols[i], "volatility30": rv[i]}
        for i in range(len(bars) - n, len(bars))
    ]
    return {"summary": s, "chart": chart, "provider": env.data.get("provider"), "meta": env.meta()}


@router.get("/{symbol}/sparkline")
async def sparkline(symbol: str, days: int = Query(30, ge=5, le=120)):
    env = await md.get_daily_history(symbol)
    bars = env.data["bars"][-days:]
    vols = [b["volume"] for b in env.data["bars"][-31:-1]]
    last_vol = bars[-1]["volume"] if bars else None
    avg = sum(vols) / len(vols) if vols else None
    return {
        "symbol": env.data["symbol"],
        "points": [{"date": b["date"], "close": b["close"]} for b in bars],
        "last_session_date": bars[-1]["date"] if bars else None,
        "last_session_volume": last_vol,
        "avg_volume_30d": avg,
        "volume_ratio": (last_vol / avg) if (avg and last_vol is not None) else None,
        "meta": env.meta(),
    }
