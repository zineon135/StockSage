"""Financial Data Service — the ONLY source of truth for market numbers.

Providers (verified against official docs, Nov 2026):
* Finnhub (free): /quote, /stock/profile2, /stock/metric, /search, /stock/market-status,
  /company-news, /news, /stock/peers. /stock/candle is premium-only, so it is NOT used
  for history by default.
* Tiingo (free "Starter": 50 req/hour, 1,000/day): end-of-day daily OHLCV history.
* Alpha Vantage (optional fallback, free: 25 req/day, last ~100 trading days only).
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

from ..config import get_settings
from ..core.cache import Envelope, cached
from ..core.errors import AppError, NotFoundError, PlanRestricted, ProviderError, ProviderNotConfigured
from ..core.http import get_json
from ..core.rate_limit import RateLimiter

FINNHUB = "https://finnhub.io/api/v1"
TIINGO = "https://api.tiingo.com"
ALPHAVANTAGE = "https://www.alphavantage.co/query"

_finnhub_limiter = RateLimiter(get_settings().finnhub_rpm, 60.0, max_wait=6.0)
_tiingo_limiter = RateLimiter(48, 3600.0, max_wait=0.0)
_av_limiter = RateLimiter(5, 60.0, max_wait=0.0)

SYMBOL_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")

# Broad-market ETFs used as transparent proxies: Finnhub's free plan does not
# provide index levels (e.g. ^GSPC), so we show the ETF that tracks each index.
INDEX_PROXIES = [
    {"symbol": "SPY", "name": "S&P 500", "proxy_note": "SPDR S&P 500 ETF (tracks the S&P 500)"},
    {"symbol": "QQQ", "name": "NASDAQ-100", "proxy_note": "Invesco QQQ (tracks the NASDAQ-100)"},
    {"symbol": "DIA", "name": "Dow Jones", "proxy_note": "SPDR Dow Jones ETF (tracks the DJIA)"},
    {"symbol": "IWM", "name": "Russell 2000", "proxy_note": "iShares Russell 2000 ETF (small caps)"},
]

# Fixed, documented universe used to compute "trending" and gainers/losers.
# Free data plans do not offer a market-wide movers feed, so rankings are computed
# from live quotes of these large, liquid US stocks.
TRACKED_UNIVERSE = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "JPM", "V",
    "UNH", "XOM", "LLY", "WMT", "MA", "JNJ", "PG", "HD", "COST", "NFLX",
    "AMD", "CRM", "BAC", "KO", "PEP", "DIS", "INTC", "ORCL", "ADBE", "PLTR",
]


def normalize_symbol(raw: str) -> str:
    s = (raw or "").strip().upper()
    if not SYMBOL_RE.match(s):
        raise AppError(f"'{raw}' is not a valid ticker symbol.", code="invalid_symbol", status_code=422)
    return s


def _finnhub_key() -> str:
    key = get_settings().finnhub_api_key
    if not key:
        raise ProviderNotConfigured("Finnhub API key is not configured. Add FINNHUB_API_KEY to backend/.env.")
    return key


async def _finnhub(path: str, **params) -> dict | list:
    # Key goes in a header so it never appears in logged URLs.
    return await get_json(
        "Finnhub", f"{FINNHUB}{path}", params=params,
        headers={"X-Finnhub-Token": _finnhub_key()}, limiter=_finnhub_limiter,
    )


def _ts(unix: int | float | None) -> str | None:
    if not unix:
        return None
    return datetime.fromtimestamp(unix, tz=timezone.utc).isoformat()


# ----------------------------------------------------------------------------- quotes

async def get_quote(symbol: str) -> Envelope:
    symbol = normalize_symbol(symbol)

    async def fetch():
        d = await _finnhub("/quote", symbol=symbol)
        if not isinstance(d, dict) or not d.get("t") or not d.get("c"):
            raise NotFoundError(f"No quote data is available for {symbol}.")
        return {
            "symbol": symbol,
            "price": d.get("c"),
            "change": d.get("d"),
            "change_pct": d.get("dp"),
            "open": d.get("o"),
            "high": d.get("h"),
            "low": d.get("l"),
            "prev_close": d.get("pc"),
            "market_time": _ts(d.get("t")),  # timestamp of the price itself (from Finnhub)
        }

    return await cached(f"quote:{symbol}", 30, "Finnhub", fetch)


async def get_quotes(symbols: list[str]) -> dict[str, Envelope | AppError]:
    import asyncio

    async def one(s):
        try:
            return s, await get_quote(s)
        except AppError as e:
            return s, e

    return dict(await asyncio.gather(*(one(s) for s in symbols)))


# ----------------------------------------------------------------------------- company

async def get_profile(symbol: str) -> Envelope:
    symbol = normalize_symbol(symbol)

    async def fetch():
        d = await _finnhub("/stock/profile2", symbol=symbol)
        if not d:
            return {"symbol": symbol, "available": False}
        return {
            "symbol": symbol,
            "available": True,
            "name": d.get("name"),
            "exchange": d.get("exchange"),
            "industry": d.get("finnhubIndustry"),
            "country": d.get("country"),
            "currency": d.get("currency"),
            "ipo": d.get("ipo"),
            "logo": d.get("logo") or None,
            "weburl": d.get("weburl") or None,
            # Finnhub reports market cap and shares outstanding in millions
            "market_cap": d["marketCapitalization"] * 1e6 if d.get("marketCapitalization") else None,
            "shares_outstanding": d["shareOutstanding"] * 1e6 if d.get("shareOutstanding") else None,
        }

    return await cached(f"profile:{symbol}", 24 * 3600, "Finnhub", fetch)


async def get_metrics(symbol: str) -> Envelope:
    symbol = normalize_symbol(symbol)

    async def fetch():
        d = await _finnhub("/stock/metric", symbol=symbol, metric="all")
        m = (d or {}).get("metric") or {}

        def g(*keys):
            for k in keys:
                if m.get(k) is not None:
                    return m[k]
            return None

        avg10 = g("10DayAverageTradingVolume")
        return {
            "symbol": symbol,
            "week52_high": g("52WeekHigh"),
            "week52_high_date": g("52WeekHighDate"),
            "week52_low": g("52WeekLow"),
            "week52_low_date": g("52WeekLowDate"),
            "pe_ttm": g("peTTM", "peBasicExclExtraTTM", "peExclExtraTTM"),
            "eps_ttm": g("epsTTM", "epsBasicExclExtraItemsTTM"),
            "beta": g("beta"),
            "dividend_yield_pct": g("currentDividendYieldTTM", "dividendYieldIndicatedAnnual"),
            "avg_volume_10d": avg10 * 1e6 if avg10 else None,  # reported in millions
            "revenue_growth_ttm_yoy_pct": g("revenueGrowthTTMYoy"),
            "net_margin_ttm_pct": g("netProfitMarginTTM"),
            "return_52w_pct": g("52WeekPriceReturnDaily"),
        }

    return await cached(f"metrics:{symbol}", 6 * 3600, "Finnhub", fetch)


async def get_peers(symbol: str) -> Envelope:
    symbol = normalize_symbol(symbol)

    async def fetch():
        d = await _finnhub("/stock/peers", symbol=symbol)
        return [p for p in (d or []) if isinstance(p, str) and p != symbol][:8]

    return await cached(f"peers:{symbol}", 24 * 3600, "Finnhub", fetch)


async def search(query: str) -> Envelope:
    q = query.strip()
    if not q or len(q) > 40:
        raise AppError("Search query must be 1–40 characters.", code="invalid_query", status_code=422)

    async def fetch():
        d = await _finnhub("/search", q=q, exchange="US")
        results = []
        for r in (d or {}).get("result", []):
            sym = r.get("symbol") or ""
            if r.get("type") not in ("Common Stock", "ETP", "ADR") or not SYMBOL_RE.match(sym):
                continue
            if "." in sym and len(sym.split(".")[-1]) > 1:
                continue  # foreign listings (e.g. AAPL.MX); keep share classes like BRK.B
            results.append({"symbol": sym, "name": r.get("description"), "type": r.get("type")})
        return results[:12]

    return await cached(f"search:{q.lower()}", 3600, "Finnhub", fetch, persist=False)


async def market_status() -> Envelope:
    async def fetch():
        d = await _finnhub("/stock/market-status", exchange="US")
        return {
            "exchange": d.get("exchange", "US"),
            "is_open": bool(d.get("isOpen")),
            "session": d.get("session"),  # pre-market | regular | post-market | null
            "holiday": d.get("holiday"),
            "timezone": d.get("timezone"),
            "as_of": _ts(d.get("t")),
        }

    return await cached("market_status", 60, "Finnhub", fetch)


async def company_news_finnhub(symbol: str, days: int = 14) -> Envelope:
    symbol = normalize_symbol(symbol)
    to = date.today()
    frm = to - timedelta(days=days)

    async def fetch():
        d = await _finnhub("/company-news", symbol=symbol, **{"from": frm.isoformat(), "to": to.isoformat()})
        return [_finnhub_article(a, symbol) for a in (d or [])[:40] if a.get("headline") and a.get("url")]

    return await cached(f"fh_news:{symbol}:{to}", 30 * 60, "Finnhub", fetch)


async def general_news_finnhub() -> Envelope:
    async def fetch():
        d = await _finnhub("/news", category="general")
        return [_finnhub_article(a, None) for a in (d or [])[:40] if a.get("headline") and a.get("url")]

    return await cached("fh_news:general", 20 * 60, "Finnhub", fetch)


def _finnhub_article(a: dict, symbol: str | None) -> dict:
    related = [s for s in (a.get("related") or "").split(",") if s]
    return {
        "title": a.get("headline"),
        "description": (a.get("summary") or "")[:400] or None,
        "url": a.get("url"),
        "publisher": a.get("source"),
        "published_at": _ts(a.get("datetime")),
        "image": a.get("image") or None,
        "tickers": [symbol] if symbol else related[:3],
        "provider": "Finnhub",
    }


# ----------------------------------------------------------------------------- history

async def _tiingo_daily(symbol: str, start: date) -> list[dict]:
    key = get_settings().tiingo_api_key
    if not key:
        raise ProviderNotConfigured("Tiingo API key is not configured. Add TIINGO_API_KEY to backend/.env.")
    tsym = symbol.replace(".", "-")
    try:
        rows = await get_json(
            "Tiingo", f"{TIINGO}/tiingo/daily/{tsym}/prices",
            params={"startDate": start.isoformat()},
            headers={"Authorization": f"Token {key}", "Content-Type": "application/json"},
            limiter=_tiingo_limiter,
        )
    except ProviderError as e:
        if "HTTP 404" in e.message:
            raise NotFoundError(f"No price history is available for {symbol}.") from e
        raise
    if not isinstance(rows, list):
        raise ProviderError("Tiingo returned an unexpected response")
    out = []
    for r in rows:
        # Adjusted values account for splits and dividends, so long-range charts
        # and indicators are not distorted by corporate actions.
        c = r.get("adjClose") or r.get("close")
        if c is None:
            continue
        out.append({
            "date": str(r["date"])[:10],
            "open": r.get("adjOpen") or r.get("open"),
            "high": r.get("adjHigh") or r.get("high"),
            "low": r.get("adjLow") or r.get("low"),
            "close": c,
            "volume": r.get("adjVolume") or r.get("volume") or 0,
        })
    return out


async def _alphavantage_daily(symbol: str) -> list[dict]:
    key = get_settings().alphavantage_api_key
    if not key:
        raise ProviderNotConfigured("No historical price provider is configured.")
    d = await get_json(
        "Alpha Vantage", ALPHAVANTAGE,
        params={"function": "TIME_SERIES_DAILY", "symbol": symbol, "outputsize": "compact", "apikey": key},
        limiter=_av_limiter,
    )
    if "Error Message" in d:
        raise NotFoundError(f"No price history is available for {symbol}.")
    if "Note" in d or "Information" in d:
        raise ProviderError("Alpha Vantage daily request limit reached")
    series = d.get("Time Series (Daily)") or {}
    return sorted(
        (
            {"date": k, "open": float(v["1. open"]), "high": float(v["2. high"]), "low": float(v["3. low"]),
             "close": float(v["4. close"]), "volume": float(v["5. volume"])}
            for k, v in series.items()
        ),
        key=lambda r: r["date"],
    )


async def get_daily_history(symbol: str) -> Envelope:
    """Up to ~5 years of daily bars (oldest first). Fetched once per symbol per day."""
    symbol = normalize_symbol(symbol)
    today = date.today()

    async def fetch():
        s = get_settings()
        errors: list[str] = []
        if s.tiingo_api_key:
            try:
                rows = await _tiingo_daily(symbol, today - timedelta(days=5 * 366))
                if rows:
                    return {"symbol": symbol, "provider": "Tiingo", "adjusted": True, "bars": rows}
                errors.append("Tiingo returned no rows")
            except NotFoundError:
                raise
            except ProviderError as e:
                errors.append(e.message)
        if s.alphavantage_api_key:
            try:
                rows = await _alphavantage_daily(symbol)
                return {"symbol": symbol, "provider": "Alpha Vantage", "adjusted": False, "bars": rows}
            except ProviderError as e:
                errors.append(e.message)
        if not s.tiingo_api_key and not s.alphavantage_api_key:
            raise ProviderNotConfigured(
                "Historical prices need a free Tiingo key (TIINGO_API_KEY) because Finnhub's free plan "
                "does not include historical candles."
            )
        raise ProviderError("; ".join(errors) or "No historical data available")

    env = await cached(f"daily:{symbol}:{today}", 12 * 3600, "Tiingo", fetch)
    env.source = env.data.get("provider", env.source) if isinstance(env.data, dict) else env.source
    return env


async def get_intraday(symbol: str) -> Envelope:
    """5-minute bars for the latest session via Tiingo IEX. Availability on free plans
    varies, so callers must handle PlanRestricted/ProviderError and hide the 1D range."""
    symbol = normalize_symbol(symbol)
    key = get_settings().tiingo_api_key
    if not key:
        raise ProviderNotConfigured("Intraday data requires TIINGO_API_KEY.")

    async def fetch():
        rows = await get_json(
            "Tiingo IEX", f"{TIINGO}/iex/{symbol.replace('.', '-')}/prices",
            params={"resampleFreq": "5min", "columns": "open,high,low,close,volume"},
            headers={"Authorization": f"Token {key}"}, limiter=_tiingo_limiter,
        )
        if not isinstance(rows, list) or not rows:
            raise PlanRestricted("Intraday data is not available for this symbol on the current plan")
        return {
            "symbol": symbol, "provider": "Tiingo (IEX)",
            "bars": [{"date": r["date"], "close": r.get("close"), "volume": r.get("volume")} for r in rows if r.get("close")],
        }

    return await cached(f"intraday:{symbol}", 5 * 60, "Tiingo (IEX)", fetch)


RANGE_DAYS = {"1W": 7, "1M": 31, "3M": 92, "6M": 183, "1Y": 366, "5Y": 5 * 366}


def slice_range(bars: list[dict], range_key: str) -> list[dict]:
    if not bars:
        return []
    days = RANGE_DAYS[range_key]
    last = date.fromisoformat(bars[-1]["date"])
    cutoff = (last - timedelta(days=days)).isoformat()
    return [b for b in bars if b["date"] >= cutoff]


def configured_providers() -> dict[str, bool]:
    s = get_settings()
    return {
        "finnhub": bool(s.finnhub_api_key),
        "tiingo": bool(s.tiingo_api_key),
        "alphavantage": bool(s.alphavantage_api_key),
        "newsapi": bool(s.newsapi_key),
        "gemini": bool(s.gemini_api_key),
        "alpaca_paper": bool(s.alpaca_api_key_id and s.alpaca_api_secret_key),
    }
