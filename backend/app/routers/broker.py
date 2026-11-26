"""Alpaca PAPER brokerage routes. No real-money trading is possible through these."""
from __future__ import annotations

import asyncio
import re
from typing import Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field, field_validator

from ..core.errors import AppError
from ..services import broker, market_data as md

router = APIRouter(prefix="/api/broker", tags=["broker"])

_ORDER_ID = re.compile(r"^[0-9a-fA-F-]{8,64}$")


@router.get("/status")
async def status():
    if not broker.configured():
        return {"configured": False, "environment": "paper"}
    acct, clk = await asyncio.gather(broker.account(), broker.clock())
    return {"configured": True, "environment": "paper", "account": acct, "clock": clk}


@router.get("/positions")
async def positions():
    return {"positions": await broker.positions()}


@router.get("/orders")
async def orders(status: Literal["open", "closed", "all"] = "all", limit: int = Query(50, ge=1, le=200)):
    return {"orders": await broker.orders(status, limit)}


class OrderRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=12)
    side: Literal["buy", "sell"]
    qty: int = Field(gt=0, le=10_000)
    type: Literal["market", "limit"] = "market"
    limit_price: float | None = Field(default=None, gt=0, le=1_000_000)
    confirm: bool = False

    @field_validator("symbol")
    @classmethod
    def _sym(cls, v: str) -> str:
        return md.normalize_symbol(v)


@router.post("/orders")
async def place(req: OrderRequest):
    if not req.confirm:
        raise AppError("Order not confirmed.", code="confirmation_required", status_code=422)
    if req.side == "sell":
        # Alpaca paper accounts allow short selling by default; Stock Sage only sells shares you hold.
        held = sum((p["qty"] or 0) for p in await broker.positions() if p["symbol"] == req.symbol and p["side"] == "long")
        open_sells = sum((o["qty"] or 0) - (o["filled_qty"] or 0) for o in await broker.orders("open", 200)
                         if o["symbol"] == req.symbol and o["side"] == "sell")
        available = held - open_sells
        if req.qty > available:
            raise AppError(
                f"You can sell at most {max(available, 0):g} {req.symbol} shares (held {held:g}, {open_sells:g} already in open sell orders). "
                "Short selling is not supported.",
                code="insufficient_shares", status_code=422,
            )
    order = await broker.place_order(req.symbol, req.side, req.qty, req.type, req.limit_price)
    return {"order": order, "environment": "paper"}


@router.delete("/orders/{order_id}")
async def cancel(order_id: str):
    if not _ORDER_ID.match(order_id):
        raise AppError("Invalid order id.", code="invalid_order_id", status_code=422)
    await broker.cancel_order(order_id)
    return {"canceled": order_id}
