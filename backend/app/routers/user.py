"""Watchlist, portfolio/paper trading and settings (persisted in the database)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.errors import AppError, NotFoundError
from ..database import get_db
from ..models import PortfolioSnapshot, UserSetting, WatchlistItem
from ..services import market_data as md, trading
from .common import DEMO_USER

router = APIRouter(prefix="/api", tags=["user"])


# ----------------------------------------------------------------------------- watchlist

class WatchIn(BaseModel):
    symbol: str = Field(min_length=1, max_length=12)


@router.get("/watchlist")
async def get_watchlist(db: Session = Depends(get_db)):
    items = db.scalars(select(WatchlistItem).where(WatchlistItem.user_id == DEMO_USER).order_by(WatchlistItem.added_at)).all()
    quotes = await md.get_quotes([i.symbol for i in items]) if items else {}
    out = []
    for i in items:
        env = quotes.get(i.symbol)
        row = {"symbol": i.symbol, "added_at": i.added_at.isoformat()}
        if isinstance(env, AppError) or env is None:
            row["error"] = {"code": env.code, "message": env.message} if env else None
        else:
            row["quote"] = env.data
            row["meta"] = env.meta()
        out.append(row)
    return {"items": out}


@router.post("/watchlist", status_code=201)
async def add_watch(body: WatchIn, db: Session = Depends(get_db)):
    symbol = md.normalize_symbol(body.symbol)
    await md.get_quote(symbol)  # validates the ticker against real data
    trading.ensure_user(db, DEMO_USER)
    exists = db.scalar(select(WatchlistItem).where(WatchlistItem.user_id == DEMO_USER, WatchlistItem.symbol == symbol))
    if not exists:
        db.add(WatchlistItem(user_id=DEMO_USER, symbol=symbol))
        db.commit()
    return {"symbol": symbol, "added": not exists}


@router.delete("/watchlist/{symbol}")
def remove_watch(symbol: str, db: Session = Depends(get_db)):
    symbol = md.normalize_symbol(symbol)
    item = db.scalar(select(WatchlistItem).where(WatchlistItem.user_id == DEMO_USER, WatchlistItem.symbol == symbol))
    if not item:
        raise NotFoundError(f"{symbol} is not on your watchlist.")
    db.delete(item)
    db.commit()
    return {"symbol": symbol, "removed": True}


# ----------------------------------------------------------------------------- portfolio

async def _valued(db: Session):
    pf = trading.get_or_create_portfolio(db, DEMO_USER)
    symbols = [h.symbol for h in pf.holdings]
    quotes = await md.get_quotes(symbols) if symbols else {}
    prices: dict[str, Decimal | None] = {}
    price_meta = {}
    for s in symbols:
        env = quotes.get(s)
        if env is None or isinstance(env, AppError):
            prices[s] = None
        else:
            prices[s] = Decimal(str(env.data["price"]))
            price_meta[s] = {"market_time": env.data["market_time"], "stale": env.stale, "change_pct": env.data["change_pct"]}
    val = trading.valuation(pf, prices)
    for h in val["holdings"]:
        h.update(price_meta.get(h["symbol"], {}))
    return pf, val


@router.get("/portfolio")
async def portfolio(db: Session = Depends(get_db)):
    pf, val = await _valued(db)
    trading.maybe_snapshot(db, pf, val)
    return {**val, "valued_at": datetime.now(timezone.utc).isoformat(), "simulated": True}


class TradeIn(BaseModel):
    symbol: str = Field(min_length=1, max_length=12)
    side: Literal["BUY", "SELL"]
    quantity: int = Field(gt=0, le=1_000_000)


def _get_fee(db: Session) -> Decimal:
    row = db.get(UserSetting, (DEMO_USER, "commission"))
    try:
        return Decimal(json.loads(row.value)) if row else Decimal("0")
    except Exception:
        return Decimal("0")


@router.post("/portfolio/trade")
async def trade(body: TradeIn, db: Session = Depends(get_db)):
    symbol = md.normalize_symbol(body.symbol)
    env = await md.get_quote(symbol)
    if env.stale:
        raise AppError("Live prices are temporarily unavailable, so simulated trades are paused to avoid using stale prices.",
                       code="stale_price", status_code=503)
    quote = trading.ExecutionQuote(
        symbol=symbol, price=Decimal(str(env.data["price"])),
        timestamp=datetime.fromisoformat(env.data["market_time"]), source=f"{env.source} quote",
    )
    pf = trading.get_or_create_portfolio(db, DEMO_USER)
    fee = _get_fee(db)
    if body.side == "BUY":
        tx = trading.execute_buy(db, pf, quote, Decimal(body.quantity), fee)
    else:
        tx = trading.execute_sell(db, pf, quote, Decimal(body.quantity), fee)
    _, val = await _valued(db)
    trading.maybe_snapshot(db, pf, val, force=True)
    return {"transaction": _tx(tx), "portfolio": val}


def _tx(t) -> dict:
    return {
        "id": t.id, "symbol": t.symbol, "side": t.side, "quantity": float(t.quantity), "price": float(t.price),
        "fee": float(t.fee), "total": float(t.total), "realized_pnl": float(t.realized_pnl) if t.realized_pnl is not None else None,
        "price_timestamp": t.price_timestamp.isoformat(), "price_source": t.price_source, "executed_at": t.executed_at.isoformat(),
    }


@router.get("/portfolio/transactions")
def transactions(db: Session = Depends(get_db)):
    pf = trading.get_or_create_portfolio(db, DEMO_USER)
    return {"transactions": [_tx(t) for t in pf.transactions]}


@router.get("/portfolio/history")
def history(db: Session = Depends(get_db)):
    pf = trading.get_or_create_portfolio(db, DEMO_USER)
    snaps = db.scalars(select(PortfolioSnapshot).where(PortfolioSnapshot.portfolio_id == pf.id).order_by(PortfolioSnapshot.taken_at)).all()
    return {
        "starting_cash": float(pf.starting_cash),
        "created_at": pf.created_at.isoformat(),
        "snapshots": [{"taken_at": s.taken_at.isoformat(), "total_value": float(s.total_value), "cash": float(s.cash),
                       "holdings_value": float(s.holdings_value)} for s in snaps],
        "note": "Snapshots are recorded when you trade or view your portfolio (at most every 15 minutes).",
    }


@router.post("/portfolio/reset")
def reset(db: Session = Depends(get_db)):
    pf = trading.get_or_create_portfolio(db, DEMO_USER)
    pf = trading.reset_portfolio(db, pf)
    return {"cash": float(pf.cash), "reset": True}


# ----------------------------------------------------------------------------- settings

DEFAULT_SETTINGS = {"display_name": "Demo Investor", "default_range": "1Y", "beginner_mode": True, "commission": 0, "show_sma": True}


class SettingsIn(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=60)
    default_range: Literal["1W", "1M", "3M", "6M", "1Y", "5Y"] | None = None
    beginner_mode: bool | None = None
    commission: float | None = Field(default=None, ge=0, le=50)
    show_sma: bool | None = None


@router.get("/settings")
def get_settings_route(db: Session = Depends(get_db)):
    rows = db.scalars(select(UserSetting).where(UserSetting.user_id == DEMO_USER)).all()
    out = dict(DEFAULT_SETTINGS)
    for r in rows:
        if r.key in out:
            out[r.key] = json.loads(r.value)
    return out


@router.put("/settings")
def put_settings(body: SettingsIn, db: Session = Depends(get_db)):
    trading.ensure_user(db, DEMO_USER)
    for k, v in body.model_dump(exclude_none=True).items():
        row = db.get(UserSetting, (DEMO_USER, k))
        if row:
            row.value = json.dumps(v)
        else:
            db.add(UserSetting(user_id=DEMO_USER, key=k, value=json.dumps(v)))
    db.commit()
    return get_settings_route(db)
