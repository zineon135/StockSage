from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..services import ai, market_data as md, news as news_svc

router = APIRouter(prefix="/api/news", tags=["news"])


@router.get("")
async def market_news(category: Literal["markets", "economy", "technology"] = "markets"):
    return await news_svc.market_news(category)


@router.get("/company/{symbol}")
async def company_news(symbol: str):
    symbol = md.normalize_symbol(symbol)
    name = None
    try:
        name = (await md.get_profile(symbol)).data.get("name")
    except Exception:
        pass
    return await news_svc.company_news(symbol, name)


class ArticleIn(BaseModel):
    id: str = Field(min_length=6, max_length=40)
    title: str = Field(min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=1000)
    publisher: str | None = Field(default=None, max_length=200)
    published_at: str | None = Field(default=None, max_length=40)
    tickers: list[str] = Field(default_factory=list, max_length=5)


class SentimentRequest(BaseModel):
    articles: list[ArticleIn] = Field(min_length=1, max_length=30)


@router.post("/sentiment")
async def sentiment(req: SentimentRequest):
    results = await ai.classify_sentiment([a.model_dump() for a in req.articles])
    return {
        "results": results,
        "note": "Sentiment is an AI classification of the headline and summary only. It describes tone, not a price forecast. "
                "Article publication times differ from market-data timestamps.",
    }
