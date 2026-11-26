from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..core.cache import cached
from ..services import ai, context, market_data as md

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.post("/analyze/{symbol}")
async def analyze(symbol: str, refresh: bool = False):
    symbol = md.normalize_symbol(symbol)

    async def fetch():
        ctx = await context.build_stock_context(symbol)
        result = await ai.analyze_stock(ctx)
        return {**result, "symbol": symbol, "company_name": ctx["company_name"],
                "sources": context.public_sources(ctx), "generated_at": ctx["generated_at"]}

    key = f"ai:analysis:{symbol}"
    if refresh:
        from ..core import cache as c

        c._mem.pop(key, None)
    env = await cached(key, 30 * 60, "Gemini", fetch, persist=not refresh)
    return {"data": env.data, "meta": env.meta()}


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=6000)


class ChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1000)
    symbol: str | None = Field(default=None, max_length=12)
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)


@router.post("/chat")
async def chat(req: ChatRequest):
    if req.symbol:
        ctx = await context.build_stock_context(req.symbol)
    else:
        ctx = await context.build_market_context()
        ctx["symbol"] = None
    result = await ai.chat(ctx, [m.model_dump() for m in req.history], req.question)
    return {**result, "symbol": ctx.get("symbol"), "sources": context.public_sources(ctx), "generated_at": ctx["generated_at"]}
