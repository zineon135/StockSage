"""Alpaca paper-broker routes against mocked HTTP responses shaped like Alpaca's Trading API v2."""
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.core import http as http_mod
from app.main import app
from app.services import broker

SEEN = []


def handler(request: httpx.Request) -> httpx.Response:
    SEEN.append(request)
    assert request.url.host == "paper-api.alpaca.markets"  # never the live API
    assert request.headers["APCA-API-KEY-ID"] == "kid" and request.headers["APCA-API-SECRET-KEY"] == "sec"
    p, m = request.url.path, request.method
    if p == "/v2/account":
        return httpx.Response(200, json={"account_number": "PA123", "status": "ACTIVE", "currency": "USD", "cash": "100000",
                                         "equity": "100000", "last_equity": "100000", "buying_power": "200000",
                                         "portfolio_value": "100000", "trading_blocked": False})
    if p == "/v2/clock":
        return httpx.Response(200, json={"is_open": False, "next_open": "2026-11-27T14:30:00Z", "next_close": "2026-11-27T18:00:00Z",
                                         "timestamp": "2026-11-25T20:00:00Z"})
    if p == "/v2/positions":
        return httpx.Response(200, json=[{"symbol": "AAPL", "qty": "3", "side": "long", "avg_entry_price": "350", "current_price": "355.58",
                                          "market_value": "1066.74", "cost_basis": "1050", "unrealized_pl": "16.74",
                                          "unrealized_plpc": "0.0159", "change_today": "0.0043"}])
    if p == "/v2/orders" and m == "POST":
        body = json.loads(request.content)
        if body["symbol"] == "TSLA":
            return httpx.Response(403, json={"code": 40310000, "message": "insufficient buying power"})
        return httpx.Response(200, json={"id": "61e69015-8549-4bfd-b9c3-01e75843f47d", "symbol": body["symbol"], "side": body["side"],
                                         "type": body["type"], "qty": body["qty"], "filled_qty": "0", "status": "accepted",
                                         "time_in_force": body["time_in_force"], "limit_price": body.get("limit_price"),
                                         "submitted_at": "2026-11-25T20:00:00Z"})
    if p == "/v2/orders":
        if request.url.params.get("status") == "open":
            return httpx.Response(200, json=[{"id": "o1", "symbol": "AAPL", "side": "sell", "qty": "1", "filled_qty": "0", "status": "new"}])
        return httpx.Response(200, json=[])
    if p.startswith("/v2/orders/") and m == "DELETE":
        return httpx.Response(204)
    return httpx.Response(404, json={"message": "not found"})


@pytest.fixture
def client(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "alpaca_api_key_id", "kid")
    monkeypatch.setattr(s, "alpaca_api_secret_key", "sec")
    mock = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(http_mod, "client", lambda: mock)
    SEEN.clear()
    with TestClient(app) as c:
        yield c


def test_paper_url_is_constant():
    assert broker.PAPER_BASE_URL == "https://paper-api.alpaca.markets"


def test_not_configured(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "alpaca_api_key_id", "")
    with TestClient(app) as c:
        assert c.get("/api/broker/status").json() == {"configured": False, "environment": "paper"}
        assert c.get("/api/broker/positions").status_code == 503


def test_status_and_positions(client):
    st = client.get("/api/broker/status").json()
    assert st["configured"] and st["account"]["buying_power"] == 200000 and st["clock"]["is_open"] is False
    pos = client.get("/api/broker/positions").json()["positions"][0]
    assert pos["qty"] == 3 and pos["unrealized_plpc"] == pytest.approx(1.59)


def test_order_requires_confirmation(client):
    r = client.post("/api/broker/orders", json={"symbol": "AAPL", "side": "buy", "qty": 1})
    assert r.status_code == 422 and r.json()["error"]["code"] == "confirmation_required"
    assert not SEEN


def test_market_and_limit_orders(client):
    r = client.post("/api/broker/orders", json={"symbol": "aapl", "side": "buy", "qty": 2, "confirm": True}).json()
    assert r["order"]["status"] == "accepted" and r["order"]["symbol"] == "AAPL"
    sent = json.loads(SEEN[-1].content)
    assert sent == {"symbol": "AAPL", "qty": "2", "side": "buy", "type": "market", "time_in_force": "day"}
    client.post("/api/broker/orders", json={"symbol": "AAPL", "side": "sell", "qty": 2, "type": "limit", "limit_price": 500.5, "confirm": True})
    assert json.loads(SEEN[-1].content)["limit_price"] == "500.50"


def test_no_short_selling(client):
    # holds 3 AAPL with 1 already in an open sell order -> at most 2 sellable
    r = client.post("/api/broker/orders", json={"symbol": "AAPL", "side": "sell", "qty": 3, "confirm": True})
    assert r.status_code == 422 and r.json()["error"]["code"] == "insufficient_shares"
    r = client.post("/api/broker/orders", json={"symbol": "MSFT", "side": "sell", "qty": 1, "confirm": True})
    assert r.status_code == 422
    assert not any(q.method == "POST" for q in SEEN)


def test_rejection_message_passed_through(client):
    r = client.post("/api/broker/orders", json={"symbol": "TSLA", "side": "buy", "qty": 1, "confirm": True})
    assert r.status_code == 422 and r.json()["error"] == {"code": "order_rejected", "message": "Alpaca: insufficient buying power", "details": None}


def test_validation(client):
    assert client.post("/api/broker/orders", json={"symbol": "AAPL", "side": "buy", "qty": 0, "confirm": True}).status_code == 422
    assert client.post("/api/broker/orders", json={"symbol": "$$$", "side": "buy", "qty": 1, "confirm": True}).status_code == 422
    assert client.post("/api/broker/orders", json={"symbol": "AAPL", "side": "buy", "qty": 1, "type": "limit", "confirm": True}).status_code == 422
    assert client.delete("/api/broker/orders/not-valid!").status_code in (404, 422)
    assert client.delete("/api/broker/orders/61e69015-8549-4bfd-b9c3-01e75843f47d").json() == {"canceled": "61e69015-8549-4bfd-b9c3-01e75843f47d"}
