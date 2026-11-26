"""Builds the verified, source-attributed context package that the AI may use.

Every item gets a stable source id (Q1, P1, M1, T1, N1…). The AI is instructed to
cite these ids, and its output is validated against them afterwards.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from ..core.errors import AppError
from . import analytics, market_data as md, news as news_svc


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _round(x, nd=4):
    if isinstance(x, float):
        return round(x, nd)
    if isinstance(x, dict):
        return {k: _round(v, nd) for k, v in x.items()}
    if isinstance(x, list):
        return [_round(v, nd) for v in x]
    return x


async def _safe(coro):
    try:
        return await coro, None
    except AppError as e:
        return None, e.message


async def technicals_for(symbol: str) -> tuple[dict | None, dict | None, str | None]:
    """Returns (technical summary without long series, history meta, error)."""
    env, err = await _safe(md.get_daily_history(symbol))
    if not env:
        return None, None, err
    bars = env.data["bars"]
    if len(bars) < 2:
        return None, None, "Not enough price history"
    tech = analytics.technical_summary(
        [b["date"] for b in bars], [b["close"] for b in bars], [b["volume"] for b in bars]
    )
    tech.pop("series", None)
    closes = [b["close"] for b in bars]
    tech["history_start"] = bars[0]["date"]
    tech["history_end"] = bars[-1]["date"]
    tech["high_1y"] = max(closes[-252:])
    tech["low_1y"] = min(closes[-252:])
    tech["return_5y_pct"] = analytics.pct_change(closes[0], closes[-1]) if len(closes) > 1000 else None
    # Monthly closes give the AI a compact view of historical patterns.
    monthly: dict[str, float] = {}
    for b in bars:
        monthly[b["date"][:7]] = b["close"]
    tech["monthly_closes_last_24"] = dict(list(monthly.items())[-24:])
    meta = {"provider": env.data.get("provider"), "adjusted": env.data.get("adjusted"), "fetched_at": env.fetched_at.isoformat(), "stale": env.stale}
    return _round(tech), meta, None


async def build_stock_context(symbol: str, *, include_news: bool = True, include_peers: bool = True) -> dict:
    symbol = md.normalize_symbol(symbol)
    (quote, qerr), (profile, perr), (metrics, merr), tech_res = await asyncio.gather(
        _safe(md.get_quote(symbol)), _safe(md.get_profile(symbol)), _safe(md.get_metrics(symbol)), technicals_for(symbol)
    )
    tech, tech_meta, terr = tech_res
    sources: list[dict] = []
    unavailable: list[str] = []

    if quote:
        sources.append({
            "id": "Q1", "kind": "quote", "title": f"{symbol} latest quote", "provider": "Finnhub",
            "url": "https://finnhub.io/", "timestamp": quote.data.get("market_time"),
            "retrieved_at": quote.fetched_at.isoformat(), "stale": quote.stale, "data": quote.data,
        })
    else:
        unavailable.append(f"Latest quote: {qerr}")
    name = None
    if profile and profile.data.get("available"):
        name = profile.data.get("name")
        sources.append({
            "id": "P1", "kind": "profile", "title": f"{name or symbol} company profile", "provider": "Finnhub",
            "url": "https://finnhub.io/", "timestamp": None, "retrieved_at": profile.fetched_at.isoformat(),
            "stale": profile.stale, "data": {k: v for k, v in profile.data.items() if k not in ("logo",)},
        })
    else:
        unavailable.append(f"Company profile: {perr or 'not provided for this symbol'}")
    if metrics:
        sources.append({
            "id": "M1", "kind": "fundamentals", "title": f"{symbol} key metrics", "provider": "Finnhub",
            "url": "https://finnhub.io/", "timestamp": None, "retrieved_at": metrics.fetched_at.isoformat(),
            "stale": metrics.stale, "data": metrics.data,
        })
    else:
        unavailable.append(f"Key metrics: {merr}")
    if tech:
        sources.append({
            "id": "T1", "kind": "technicals",
            "title": f"{symbol} technical indicators (computed by Stock Sage from {tech_meta['provider']} daily prices)",
            "provider": f"Stock Sage Analytics / {tech_meta['provider']}", "url": None,
            "timestamp": tech.get("as_of"), "retrieved_at": tech_meta["fetched_at"], "stale": tech_meta["stale"],
            "data": tech,
        })
    else:
        unavailable.append(f"Price history & technical indicators: {terr}")

    if include_peers:
        peers_env, _ = await _safe(md.get_peers(symbol))
        if peers_env and peers_env.data:
            peer_syms = peers_env.data[:4]
            peer_quotes = await md.get_quotes(peer_syms)
            pdata = {}
            for s, env in peer_quotes.items():
                if not isinstance(env, AppError):
                    pdata[s] = {"price": env.data["price"], "change_pct": env.data["change_pct"], "market_time": env.data["market_time"]}
            if pdata:
                sources.append({
                    "id": "C1", "kind": "peers", "title": f"Peer companies of {symbol} (latest quotes)", "provider": "Finnhub",
                    "url": "https://finnhub.io/", "timestamp": None, "retrieved_at": _now(), "stale": False, "data": pdata,
                })

    if include_news:
        news, nerr = await _safe(news_svc.company_news(symbol, name))
        if news and news["articles"]:
            for i, a in enumerate(news["articles"][:12], start=1):
                sources.append({
                    "id": f"N{i}", "kind": "news", "title": a["title"], "provider": a["provider"],
                    "publisher": a.get("publisher"), "url": a["url"], "timestamp": a.get("published_at"),
                    "retrieved_at": _now(), "stale": False,
                    "data": {"headline": a["title"], "summary": a.get("description"), "publisher": a.get("publisher")},
                })
        else:
            unavailable.append(f"Recent news: {nerr or 'no recent articles found'}")

    return {
        "symbol": symbol,
        "company_name": name,
        "generated_at": _now(),
        "sources": sources,
        "unavailable": unavailable,
    }


async def build_market_context() -> dict:
    sources: list[dict] = []
    unavailable: list[str] = []
    idx = await md.get_quotes([p["symbol"] for p in md.INDEX_PROXIES])
    idx_data = {}
    for p in md.INDEX_PROXIES:
        env = idx[p["symbol"]]
        if not isinstance(env, AppError):
            idx_data[p["symbol"]] = {"tracks": p["name"], **{k: env.data[k] for k in ("price", "change_pct", "market_time")}}
    if idx_data:
        sources.append({"id": "I1", "kind": "indices", "title": "Broad-market ETF quotes (index proxies)", "provider": "Finnhub",
                        "url": "https://finnhub.io/", "timestamp": None, "retrieved_at": _now(), "stale": False, "data": idx_data})
    else:
        unavailable.append("Index proxy quotes")

    uni = await md.get_quotes(md.TRACKED_UNIVERSE)
    movers = []
    for s, env in uni.items():
        if not isinstance(env, AppError) and env.data.get("change_pct") is not None:
            movers.append({"symbol": s, "price": env.data["price"], "change_pct": round(env.data["change_pct"], 2), "market_time": env.data["market_time"]})
    movers.sort(key=lambda m: m["change_pct"], reverse=True)
    if movers:
        sources.append({"id": "U1", "kind": "movers",
                        "title": f"Daily moves across Stock Sage's tracked universe of {len(md.TRACKED_UNIVERSE)} large-cap US stocks",
                        "provider": "Finnhub", "url": "https://finnhub.io/", "timestamp": None, "retrieved_at": _now(), "stale": False,
                        "data": {"sorted_by_change_pct_desc": movers}})
    else:
        unavailable.append("Tracked-universe quotes")

    news, nerr = await _safe(news_svc.market_news("markets"))
    if news and news["articles"]:
        for i, a in enumerate(news["articles"][:15], start=1):
            sources.append({"id": f"N{i}", "kind": "news", "title": a["title"], "provider": a["provider"], "publisher": a.get("publisher"),
                            "url": a["url"], "timestamp": a.get("published_at"), "retrieved_at": _now(), "stale": False,
                            "data": {"headline": a["title"], "summary": a.get("description"), "publisher": a.get("publisher")}})
    else:
        unavailable.append(f"Market news: {nerr or 'none found'}")
    return {"generated_at": _now(), "sources": sources, "unavailable": unavailable}


def public_sources(ctx: dict) -> list[dict]:
    """Sources as returned to the browser (without bulky raw data)."""
    return [{k: v for k, v in s.items() if k != "data"} for s in ctx["sources"]]
