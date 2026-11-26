"""News service: NewsAPI (primary) + Finnhub news (free, complementary).

NewsAPI Developer plan (verified Nov 2026): 100 requests/day, articles delayed by
24h, search window ~1 month, development use only (production requires a paid plan).
Only metadata is shown (headline, short description, publisher, date, link) —
never full article text — with a link to the original publisher.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import date, timedelta
from urllib.parse import urlsplit

from ..config import get_settings
from ..core.cache import cached
from ..core.errors import AppError, ProviderError, ProviderNotConfigured
from ..core.http import get_json
from ..core.rate_limit import RateLimiter
from . import market_data as md

log = logging.getLogger("stocksage.news")
NEWSAPI = "https://newsapi.org/v2"
_newsapi_limiter = RateLimiter(20, 3600.0, max_wait=0.0)  # protect the 100/day budget

CATEGORIES = {"markets", "company", "economy", "technology"}


def article_id(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()[:12]


def _key() -> str:
    k = get_settings().newsapi_key
    if not k:
        raise ProviderNotConfigured("NewsAPI key is not configured. Add NEWSAPI_KEY to backend/.env.")
    return k


def _newsapi_article(a: dict, ticker: str | None) -> dict | None:
    if not a.get("title") or not a.get("url") or a.get("title") == "[Removed]":
        return None
    return {
        "title": a["title"],
        "description": (a.get("description") or "")[:400] or None,
        "url": a["url"],
        "publisher": (a.get("source") or {}).get("name"),
        "published_at": a.get("publishedAt"),
        "image": a.get("urlToImage") or None,
        "tickers": [ticker] if ticker else [],
        "provider": "NewsAPI",
    }


# Sites seen in live NewsAPI results that are not news (e.g. software-release blogs matching "stocks"/"earnings").
NEWSAPI_EXCLUDED_DOMAINS = "rlsbb.cc,rlsbb.ru,rlsbb.to"


async def _newsapi(path: str, params: dict) -> list[dict]:
    if path == "/everything":
        params = {**params, "excludeDomains": NEWSAPI_EXCLUDED_DOMAINS}
    d = await get_json("NewsAPI", f"{NEWSAPI}{path}", params=params, headers={"X-Api-Key": _key()}, limiter=_newsapi_limiter)
    if d.get("status") != "ok":
        raise ProviderError(f"NewsAPI error: {d.get('message', 'unknown')}")
    excluded = tuple(NEWSAPI_EXCLUDED_DOMAINS.split(","))
    out = []
    for a in d.get("articles") or []:
        host = (urlsplit(str(a.get("url") or "")).hostname or "").lower()
        if any(host == dom or host.endswith("." + dom) for dom in excluded):
            continue
        out.append(a)
    return out


def _dedupe_sort(articles: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out = []
    for a in articles:
        norm = (a["title"] or "").strip().lower()[:90]
        if a["url"] in seen or norm in seen:
            continue
        seen.update({a["url"], norm})
        a["id"] = article_id(a["url"])
        out.append(a)
    out.sort(key=lambda a: a.get("published_at") or "", reverse=True)
    return out


async def market_news(category: str = "markets") -> dict:
    """General / market / economy / technology news from all configured providers."""
    if category not in CATEGORIES - {"company"}:
        raise AppError("Unknown news category.", code="invalid_category", status_code=422)
    articles: list[dict] = []
    sources_meta: list[dict] = []
    errors: list[str] = []

    if get_settings().newsapi_key:
        async def fetch_newsapi():
            if category == "markets":
                # top-headlines?category=business mixes in general world news, so search market terms instead.
                raw = await _newsapi("/everything", {
                    "q": '("stock market" OR stocks OR "Wall Street" OR "S&P 500" OR Nasdaq OR "Dow Jones" OR earnings)',
                    "searchIn": "title,description", "language": "en", "sortBy": "publishedAt", "pageSize": 40,
                })
            elif category == "technology":
                raw = await _newsapi("/top-headlines", {"country": "us", "category": "technology", "pageSize": 40})
            else:
                raw = await _newsapi("/everything", {
                    "q": '(inflation OR "interest rates" OR "Federal Reserve" OR GDP OR "jobs report" OR CPI)',
                    "searchIn": "title,description", "language": "en", "sortBy": "publishedAt", "pageSize": 40,
                })
            return [x for x in (_newsapi_article(a, None) for a in raw) if x]

        try:
            env = await cached(f"newsapi:{category}", 45 * 60, "NewsAPI", fetch_newsapi)
            articles += env.data
            sources_meta.append(env.meta())
        except AppError as e:
            errors.append(f"NewsAPI: {e.message}")

    if category in ("markets", "economy") and get_settings().finnhub_api_key:
        try:
            env = await md.general_news_finnhub()
            articles += [dict(a) for a in env.data]
            sources_meta.append(env.meta())
        except AppError as e:
            errors.append(f"Finnhub: {e.message}")

    if not articles and errors:
        raise ProviderError("; ".join(errors))
    if not articles and not sources_meta:
        raise ProviderNotConfigured("No news provider is configured. Add NEWSAPI_KEY and/or FINNHUB_API_KEY.")
    return {"articles": _dedupe_sort(articles)[:50], "sources": sources_meta, "warnings": errors}


async def company_news(symbol: str, company_name: str | None = None) -> dict:
    symbol = md.normalize_symbol(symbol)
    articles: list[dict] = []
    sources_meta: list[dict] = []
    errors: list[str] = []

    if get_settings().finnhub_api_key:
        try:
            env = await md.company_news_finnhub(symbol)
            articles += [dict(a) for a in env.data]
            sources_meta.append(env.meta())
        except AppError as e:
            errors.append(f"Finnhub: {e.message}")

    if get_settings().newsapi_key:
        name = (company_name or "").replace(",", " ").replace(" Inc", "").replace(".", " ").strip()
        q = f'"{symbol}"' + (f' OR "{name}"' if name else "")

        async def fetch_newsapi():
            raw = await _newsapi("/everything", {
                "q": q, "language": "en", "sortBy": "publishedAt", "pageSize": 30,
                "from": (date.today() - timedelta(days=28)).isoformat(),
                "searchIn": "title,description",
            })
            return [x for x in (_newsapi_article(a, symbol) for a in raw) if x]

        try:
            env = await cached(f"newsapi:co:{symbol}:{date.today()}", 2 * 3600, "NewsAPI", fetch_newsapi)
            articles += env.data
            sources_meta.append(env.meta())
        except AppError as e:
            errors.append(f"NewsAPI: {e.message}")

    if not articles and errors:
        raise ProviderError("; ".join(errors))
    if not articles and not sources_meta:
        raise ProviderNotConfigured("No news provider is configured. Add NEWSAPI_KEY and/or FINNHUB_API_KEY.")
    return {"articles": _dedupe_sort(articles)[:40], "sources": sources_meta, "warnings": errors}
