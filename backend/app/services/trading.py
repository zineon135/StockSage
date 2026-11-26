"""Paper-trading engine. Pure simulation with virtual funds — no brokerage access.

All money math uses ``Decimal`` to avoid floating-point drift. The market price is
supplied by the caller (retrieved from the financial data service) so this module
contains only deterministic, testable accounting logic.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..core.errors import AppError
from ..models import Holding, Portfolio, PortfolioSnapshot, Transaction, User

CENT = Decimal("0.01")
PRICE_Q = Decimal("0.0001")
QTY_Q = Decimal("0.000001")
MAX_QTY = Decimal("1000000")


@dataclass(frozen=True)
class ExecutionQuote:
    symbol: str
    price: Decimal
    timestamp: datetime
    source: str


def money(x: Decimal) -> Decimal:
    return x.quantize(CENT, rounding=ROUND_HALF_UP)


def to_decimal(x: float | int | str | Decimal) -> Decimal:
    return x if isinstance(x, Decimal) else Decimal(str(x))


def ensure_user(db: Session, user_id: str) -> User:
    user = db.get(User, user_id)
    if not user:
        user = User(id=user_id)
        db.add(user)
        db.flush()
    return user


def get_or_create_portfolio(db: Session, user_id: str) -> Portfolio:
    ensure_user(db, user_id)
    pf = db.scalar(select(Portfolio).where(Portfolio.user_id == user_id))
    if not pf:
        start = money(to_decimal(get_settings().starting_cash))
        pf = Portfolio(user_id=user_id, starting_cash=start, cash=start, realized_pnl=Decimal("0"))
        db.add(pf)
        db.commit()
        db.refresh(pf)
    return pf


def validate_quantity(quantity: Decimal) -> Decimal:
    q = to_decimal(quantity)
    if q <= 0:
        raise AppError("Quantity must be greater than zero.", code="invalid_quantity")
    if q > MAX_QTY:
        raise AppError("Quantity is too large for a single order.", code="invalid_quantity")
    if q != q.to_integral_value():
        raise AppError("Stock Sage simulates whole-share orders only.", code="invalid_quantity")
    return q.quantize(QTY_Q)


def _holding(pf: Portfolio, symbol: str) -> Holding | None:
    return next((h for h in pf.holdings if h.symbol == symbol), None)


def execute_buy(db: Session, pf: Portfolio, quote: ExecutionQuote, quantity: Decimal, fee: Decimal = Decimal("0")) -> Transaction:
    qty = validate_quantity(quantity)
    price = quote.price.quantize(PRICE_Q)
    if price <= 0:
        raise AppError("No valid market price is available for this stock.", code="invalid_price")
    fee = money(to_decimal(fee))
    cost = money(price * qty) + fee
    if cost > pf.cash:
        raise AppError(
            f"Insufficient virtual cash. This order costs ${cost:,.2f} but you have ${pf.cash:,.2f} available.",
            code="insufficient_funds",
        )

    h = _holding(pf, quote.symbol)
    if h:
        total_cost_basis = h.avg_cost * h.quantity + price * qty + fee
        h.quantity = (h.quantity + qty).quantize(QTY_Q)
        h.avg_cost = (total_cost_basis / h.quantity).quantize(PRICE_Q)
    else:
        h = Holding(symbol=quote.symbol, quantity=qty, avg_cost=((price * qty + fee) / qty).quantize(PRICE_Q))
        pf.holdings.append(h)

    pf.cash = money(pf.cash - cost)
    tx = Transaction(
        symbol=quote.symbol, side="BUY", quantity=qty, price=price, fee=fee, total=cost,
        realized_pnl=None, price_timestamp=quote.timestamp, price_source=quote.source,
    )
    pf.transactions.append(tx)
    db.commit()
    db.refresh(tx)
    return tx


def execute_sell(db: Session, pf: Portfolio, quote: ExecutionQuote, quantity: Decimal, fee: Decimal = Decimal("0")) -> Transaction:
    qty = validate_quantity(quantity)
    h = _holding(pf, quote.symbol)
    if not h or h.quantity < qty:
        owned = h.quantity if h else Decimal("0")
        raise AppError(
            f"You own {owned.normalize():f} shares of {quote.symbol}; cannot sell {qty.normalize():f}.",
            code="insufficient_shares",
        )
    price = quote.price.quantize(PRICE_Q)
    if price <= 0:
        raise AppError("No valid market price is available for this stock.", code="invalid_price")
    fee = money(to_decimal(fee))
    proceeds = money(price * qty) - fee
    realized = money((price - h.avg_cost) * qty - fee)

    h.quantity = (h.quantity - qty).quantize(QTY_Q)
    if h.quantity == 0:
        pf.holdings.remove(h)
        db.delete(h)

    pf.cash = money(pf.cash + proceeds)
    pf.realized_pnl = money(pf.realized_pnl + realized)
    tx = Transaction(
        symbol=quote.symbol, side="SELL", quantity=qty, price=price, fee=fee, total=proceeds,
        realized_pnl=realized, price_timestamp=quote.timestamp, price_source=quote.source,
    )
    pf.transactions.append(tx)
    db.commit()
    db.refresh(tx)
    return tx


def valuation(pf: Portfolio, prices: dict[str, Decimal | None]) -> dict:
    """Compute portfolio analytics given current prices (``None`` = unavailable)."""
    holdings = []
    holdings_value = Decimal("0")
    cost_basis_total = Decimal("0")
    unpriced = []
    for h in sorted(pf.holdings, key=lambda x: x.symbol):
        cost = h.avg_cost * h.quantity
        cost_basis_total += cost
        p = prices.get(h.symbol)
        if p is None:
            unpriced.append(h.symbol)
            # value at cost so totals remain meaningful; flagged in UI
            mv = cost
        else:
            mv = p * h.quantity
        holdings_value += mv
        holdings.append({
            "symbol": h.symbol,
            "quantity": float(h.quantity),
            "avg_cost": float(h.avg_cost),
            "price": float(p) if p is not None else None,
            "market_value": float(money(mv)),
            "cost_basis": float(money(cost)),
            "unrealized_pnl": float(money(mv - cost)) if p is not None else None,
            "unrealized_pnl_pct": float((mv / cost - 1) * 100) if (p is not None and cost) else None,
        })
    total = pf.cash + holdings_value
    for row in holdings:
        row["allocation_pct"] = float(Decimal(str(row["market_value"])) / total * 100) if total else 0.0
    unrealized = sum((Decimal(str(r["unrealized_pnl"])) for r in holdings if r["unrealized_pnl"] is not None), Decimal("0"))
    return {
        "starting_cash": float(pf.starting_cash),
        "cash": float(money(pf.cash)),
        "holdings_value": float(money(holdings_value)),
        "total_value": float(money(total)),
        "invested_cost_basis": float(money(cost_basis_total)),
        "unrealized_pnl": float(money(unrealized)),
        "realized_pnl": float(money(pf.realized_pnl)),
        "total_return": float(money(total - pf.starting_cash)),
        "total_return_pct": float((total / pf.starting_cash - 1) * 100) if pf.starting_cash else 0.0,
        "holdings": holdings,
        "unpriced_symbols": unpriced,
    }


def maybe_snapshot(db: Session, pf: Portfolio, val: dict, min_interval_minutes: int = 15, force: bool = False) -> None:
    """Store a portfolio value snapshot (throttled) to build performance history."""
    if val["unpriced_symbols"]:
        return  # never record a snapshot built on missing prices
    last = db.scalar(
        select(PortfolioSnapshot).where(PortfolioSnapshot.portfolio_id == pf.id).order_by(PortfolioSnapshot.taken_at.desc())
    )
    now = datetime.now(timezone.utc)
    if last and not force:
        taken = last.taken_at if last.taken_at.tzinfo else last.taken_at.replace(tzinfo=timezone.utc)
        if now - taken < timedelta(minutes=min_interval_minutes):
            return
    db.add(PortfolioSnapshot(
        portfolio_id=pf.id, taken_at=now, cash=to_decimal(val["cash"]),
        holdings_value=to_decimal(val["holdings_value"]), total_value=to_decimal(val["total_value"]),
    ))
    db.commit()


def reset_portfolio(db: Session, pf: Portfolio) -> Portfolio:
    user_id = pf.user_id
    db.delete(pf)
    db.commit()
    return get_or_create_portfolio(db, user_id)
