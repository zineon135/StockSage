import asyncio
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.core import cache
from app.core.cache import Envelope
from app.core.errors import ProviderError, ProviderNotConfigured
from app.main import app
from app.services import market_data as md


def test_stale_fallback_after_provider_failure():
    cache.clear_memory_cache()
    calls = {"n": 0}

    async def ok():
        calls["n"] += 1
        return {"v": 1}

    async def boom():
        raise ProviderError("down")

    first = asyncio.run(cache.cached("t:stale", 0.0, "TestProv", ok))
    assert not first.stale
    second = asyncio.run(cache.cached("t:stale", 0.0, "TestProv", boom))
    assert second.stale and second.data == {"v": 1}
    assert second.fetched_at == first.fetched_at  # original timestamp preserved
    assert "unavailable" in second.stale_reason


def test_no_fallback_raises():
    cache.clear_memory_cache()

    async def boom():
        raise ProviderError("down")

    with pytest.raises(ProviderError):
        asyncio.run(cache.cached("t:none", 10, "TestProv", boom))


@pytest.fixture
def client(monkeypatch):
    async def fake_quote(symbol):
        symbol = md.normalize_symbol(symbol)
        if symbol == "ZZZZ":
            from app.core.errors import NotFoundError
            raise NotFoundError("No quote data")
        return Envelope(
            data={"symbol": symbol, "price": 100.0, "change": 1.0, "change_pct": 1.0, "open": 99, "high": 101, "low": 98,
                  "prev_close": 99.0, "market_time": "2026-11-24T21:00:00+00:00"},
            source="Finnhub", fetched_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr(md, "get_quote", fake_quote)
    with TestClient(app) as c:
        c.post("/api/portfolio/reset")
        for item in c.get("/api/watchlist").json()["items"]:
            c.delete(f"/api/watchlist/{item['symbol']}")
        yield c


def test_system_status(client):
    r = client.get("/api/system/status")
    assert r.status_code == 200
    body = r.json()
    assert "disclaimer" in body and set(body["providers"]) >= {"finnhub", "tiingo", "newsapi", "gemini"}
    # Keys themselves must never be exposed
    assert all(isinstance(v, bool) for v in body["providers"].values())


def test_trade_flow(client):
    r = client.post("/api/portfolio/trade", json={"symbol": "aapl", "side": "BUY", "quantity": 10})
    assert r.status_code == 200, r.text
    assert r.json()["transaction"]["total"] == 1000.0
    pf = client.get("/api/portfolio").json()
    assert pf["cash"] == 99000.0 and pf["holdings"][0]["symbol"] == "AAPL"
    r = client.post("/api/portfolio/trade", json={"symbol": "AAPL", "side": "SELL", "quantity": 11})
    assert r.status_code == 400 and r.json()["error"]["code"] == "insufficient_shares"
    tx = client.get("/api/portfolio/transactions").json()["transactions"]
    assert len(tx) == 1 and tx[0]["price_timestamp"].startswith("2026-11-24")


def test_trade_validation(client):
    r = client.post("/api/portfolio/trade", json={"symbol": "AAPL", "side": "BUY", "quantity": 0})
    assert r.status_code == 422
    r = client.post("/api/portfolio/trade", json={"symbol": "$$$", "side": "BUY", "quantity": 1})
    assert r.status_code == 422


def test_watchlist_persistence(client):
    assert client.post("/api/watchlist", json={"symbol": "msft"}).status_code == 201
    assert client.post("/api/watchlist", json={"symbol": "ZZZZ"}).status_code == 404
    items = client.get("/api/watchlist").json()["items"]
    assert [i["symbol"] for i in items] == ["MSFT"]
    assert client.delete("/api/watchlist/MSFT").status_code == 200


def test_settings_roundtrip(client):
    r = client.put("/api/settings", json={"default_range": "6M", "commission": 1.5})
    assert r.json()["default_range"] == "6M"
    assert client.put("/api/settings", json={"default_range": "10Y"}).status_code == 422
    client.put("/api/settings", json={"default_range": "1Y", "commission": 0})


def test_history_not_configured_returns_503(client, monkeypatch):
    async def nf(symbol):
        raise ProviderNotConfigured("Tiingo API key is not configured.")

    monkeypatch.setattr(md, "get_daily_history", nf)
    r = client.get("/api/stocks/AAPL/history?range=1Y")
    assert r.status_code == 503 and r.json()["error"]["code"] == "provider_not_configured"
