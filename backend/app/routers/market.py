from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from ..core.cache import cached
from ..core.errors import AppError, ProviderError
from ..services import ai, context, market_data as md
from .common import section

router = APIRouter(prefix="/api/market", tags=["market"])

UNIVERSE_NAMES = {
    "AAPL": "Apple", "MSFT": "Microsoft", "NVDA": "NVIDIA", "AMZN": "Amazon", "GOOGL": "Alphabet", "META": "Meta Platforms",
    "TSLA": "Tesla", "AVGO": "Broadcom", "JPM": "JPMorgan Chase", "V": "Visa", "UNH": "UnitedHealth", "XOM": "Exxon Mobil",
    "LLY": "Eli Lilly", "WMT": "Walmart", "MA": "Mastercard", "JNJ": "Johnson & Johnson", "PG": "Procter & Gamble",
    "HD": "Home Depot", "COST": "Costco", "NFLX": "Netflix", "AMD": "AMD", "CRM": "Salesforce", "BAC": "Bank of America",
    "KO": "Coca-Cola", "PEP": "PepsiCo", "DIS": "Disney", "INTC": "Intel", "ORCL": "Oracle", "ADBE": "Adobe", "PLTR": "Palantir",
}


@router.get("/status")
async def status():
    return await section(md.market_status())


@router.get("/overview")
async def overview():
    quotes = await md.get_quotes([p["symbol"] for p in md.INDEX_PROXIES])
    items = []
    for p in md.INDEX_PROXIES:
        env = quotes[p["symbol"]]
        if isinstance(env, AppError):
            items.append({**p, "error": {"code": env.code, "message": env.message}})
        else:
            items.append({**p, "quote": env.data, "meta": env.meta()})
    return {"indices": items, "status": await section(md.market_status())}


@router.get("/movers")
async def movers():
    quotes = await md.get_quotes(md.TRACKED_UNIVERSE)
    rows, errors, stale = [], [], False
    for s, env in quotes.items():
        if isinstance(env, AppError):
            errors.append({"symbol": s, "message": env.message})
            continue
        q = env.data
        if q.get("change_pct") is None:
            continue
        stale = stale or env.stale
        rows.append({"symbol": s, "name": UNIVERSE_NAMES.get(s, s), "price": q["price"], "change": q["change"],
                     "change_pct": q["change_pct"], "market_time": q["market_time"], "stale": env.stale})
    if not rows:
        first = next((e for e in quotes.values() if isinstance(e, AppError)), None)
        if first:
            raise first
    up = sum(1 for r in rows if r["change_pct"] > 0)
    down = sum(1 for r in rows if r["change_pct"] < 0)
    by_abs = sorted(rows, key=lambda r: abs(r["change_pct"]), reverse=True)
    return {
        "universe_size": len(md.TRACKED_UNIVERSE),
        "universe_note": "Rankings are computed from live quotes of a fixed list of large, liquid US stocks — "
                         "not the entire market (free data plans do not include market-wide movers).",
        "trending": by_abs[:8],
        "gainers": sorted([r for r in rows if r["change_pct"] > 0], key=lambda r: -r["change_pct"])[:5],
        "losers": sorted([r for r in rows if r["change_pct"] < 0], key=lambda r: r["change_pct"])[:5],
        "breadth": {"advancing": up, "declining": down, "unchanged": len(rows) - up - down},
        "all": sorted(rows, key=lambda r: r["symbol"]),
        "errors": errors,
        "stale": stale,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/insights")
async def insights():
    async def fetch():
        ctx = await context.build_market_context()
        if not ctx["sources"]:
            raise ProviderError("No market data available to analyze")
        result = await ai.market_insights(ctx)
        return {**result, "sources": context.public_sources(ctx), "generated_at": ctx["generated_at"]}

    env = await cached("ai:market_insights", 30 * 60, "Gemini", fetch)
    return {"data": env.data, "meta": env.meta()}
