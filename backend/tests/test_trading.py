from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.core.errors import AppError
from app.database import SessionLocal, init_db
from app.services import trading as t

init_db()


def q(symbol: str, price: str) -> t.ExecutionQuote:
    return t.ExecutionQuote(symbol=symbol, price=Decimal(price), timestamp=datetime.now(timezone.utc), source="test")


@pytest.fixture
def db_pf():
    db = SessionLocal()
    pf = t.get_or_create_portfolio(db, "pytest-user")
    pf = t.reset_portfolio(db, pf)
    yield db, pf
    db.close()


def test_starts_with_100k(db_pf):
    _, pf = db_pf
    assert pf.cash == Decimal("100000.00")


def test_buy_updates_cash_and_holding(db_pf):
    db, pf = db_pf
    tx = t.execute_buy(db, pf, q("AAPL", "190.1234"), Decimal(10))
    assert tx.total == Decimal("1901.23")
    assert pf.cash == Decimal("98098.77")
    h = pf.holdings[0]
    assert h.quantity == 10 and h.avg_cost == Decimal("190.1234")


def test_weighted_average_cost(db_pf):
    db, pf = db_pf
    t.execute_buy(db, pf, q("MSFT", "100"), Decimal(10))
    t.execute_buy(db, pf, q("MSFT", "200"), Decimal(30))
    assert pf.holdings[0].avg_cost == Decimal("175.0000")
    assert pf.holdings[0].quantity == 40


def test_sell_realizes_pnl_and_removes_empty_holding(db_pf):
    db, pf = db_pf
    t.execute_buy(db, pf, q("NVDA", "100"), Decimal(10))
    tx = t.execute_sell(db, pf, q("NVDA", "120"), Decimal(10))
    assert tx.realized_pnl == Decimal("200.00")
    assert pf.realized_pnl == Decimal("200.00")
    assert pf.cash == Decimal("100200.00")
    assert pf.holdings == []


def test_insufficient_funds(db_pf):
    db, pf = db_pf
    with pytest.raises(AppError) as e:
        t.execute_buy(db, pf, q("BRK.A", "700000"), Decimal(1))
    assert e.value.code == "insufficient_funds"
    assert pf.cash == Decimal("100000.00")


def test_cannot_oversell(db_pf):
    db, pf = db_pf
    t.execute_buy(db, pf, q("AMD", "50"), Decimal(2))
    with pytest.raises(AppError) as e:
        t.execute_sell(db, pf, q("AMD", "50"), Decimal(3))
    assert e.value.code == "insufficient_shares"


@pytest.mark.parametrize("bad", [Decimal(0), Decimal(-1), Decimal("1.5"), Decimal("2000000")])
def test_invalid_quantities(db_pf, bad):
    db, pf = db_pf
    with pytest.raises(AppError):
        t.execute_buy(db, pf, q("AAPL", "10"), bad)


def test_valuation(db_pf):
    db, pf = db_pf
    t.execute_buy(db, pf, q("AAPL", "100"), Decimal(10))
    t.execute_buy(db, pf, q("TSLA", "200"), Decimal(5))
    v = t.valuation(pf, {"AAPL": Decimal("110"), "TSLA": None})
    assert v["cash"] == 98000.0
    assert v["unpriced_symbols"] == ["TSLA"]
    aapl = next(h for h in v["holdings"] if h["symbol"] == "AAPL")
    assert aapl["unrealized_pnl"] == 100.0
    assert v["total_value"] == pytest.approx(98000 + 1100 + 1000)
