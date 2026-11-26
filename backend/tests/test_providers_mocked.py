"""Integration tests for provider clients using mocked HTTP responses shaped like each
provider's documented format. These verify parsing, error mapping and the AI
pipeline end-to-end WITHOUT real API keys; they are not a substitute for live tests."""
import json
from datetime import date, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.core import cache, http as http_mod
from app.main import app


def _bars(n=300):
    start = date.today() - timedelta(days=n)
    out = []
    for i in range(n):
        p = 100 + i * 0.2
        out.append({"date": f"{(start + timedelta(days=i)).isoformat()}T00:00:00.000Z", "open": p, "high": p + 1, "low": p - 1,
                    "close": p, "volume": 1_000_000 + i, "adjOpen": p, "adjHigh": p + 1, "adjLow": p - 1, "adjClose": p,
                    "adjVolume": 1_000_000 + i, "divCash": 0.0, "splitFactor": 1.0})
    return out


GEMINI_CALLS = []


def handler(request: httpx.Request) -> httpx.Response:
    url = str(request.url)
    if "finnhub.io" in url:
        assert request.headers.get("X-Finnhub-Token") == "fh-test"
        assert "token=" not in url  # key never in URL
        path = request.url.path
        sym = request.url.params.get("symbol")
        if path.endswith("/quote"):
            if sym == "NOPE":
                return httpx.Response(200, json={"c": 0, "d": None, "dp": None, "h": 0, "l": 0, "o": 0, "pc": 0, "t": 0})
            return httpx.Response(200, json={"c": 231.45, "d": 2.82, "dp": 1.2334, "h": 232, "l": 228, "o": 229, "pc": 228.63, "t": 1764018000})
        if path.endswith("/stock/profile2"):
            return httpx.Response(200, json={"name": "Apple Inc", "exchange": "NASDAQ NMS - GLOBAL MARKET", "finnhubIndustry": "Technology",
                                             "marketCapitalization": 3450000.0, "shareOutstanding": 14900.0, "ticker": sym, "country": "US"})
        if path.endswith("/stock/metric"):
            return httpx.Response(200, json={"metric": {"52WeekHigh": 260.1, "52WeekLow": 169.2, "peTTM": 35.1, "beta": 1.2, "10DayAverageTradingVolume": 52.5}})
        if path.endswith("/stock/peers"):
            return httpx.Response(200, json=["AAPL", "MSFT", "DELL"])
        if path.endswith("/company-news"):
            return httpx.Response(200, json=[{"headline": "Apple unveils new chip", "summary": "Details...", "url": "https://example.com/a1",
                                              "source": "Reuters", "datetime": 1764000000, "related": "AAPL", "image": ""}])
        if path.endswith("/search"):
            return httpx.Response(200, json={"count": 2, "result": [{"symbol": "AAPL", "description": "APPLE INC", "type": "Common Stock"},
                                                                    {"symbol": "AAPL.MX", "description": "APPLE INC", "type": "Common Stock"}]})
        return httpx.Response(404)
    if "api.tiingo.com" in url:
        assert request.headers["Authorization"] == "Token tg-test"
        if "/ZZZZ/" in url:
            return httpx.Response(404, json={"detail": "Error: Ticker 'ZZZZ' not found"})
        return httpx.Response(200, json=_bars())
    if "newsapi.org" in url:
        assert request.headers["X-Api-Key"] == "na-test"
        return httpx.Response(200, json={"status": "ok", "articles": [
            {"title": "Apple shares rise", "description": "Desc", "url": "https://example.com/n1", "source": {"name": "CNBC"}, "publishedAt": "2026-11-24T15:00:00Z"},
            {"title": "[Removed]", "url": "https://removed"},
        ]})
    if "generativelanguage.googleapis.com" in url:
        assert request.headers["x-goog-api-key"] == "gm-test"
        body = json.loads(request.content)
        GEMINI_CALLS.append(body)
        assert body["generationConfig"]["responseMimeType"] == "application/json"
        schema = body["generationConfig"]["responseJsonSchema"]
        if "sections" in json.dumps(schema) or "company_overview" in schema["properties"]:
            sec = {"summary": "Apple traded at $231.45 [Q1].", "points": [
                {"text": "Price was $231.45, up 1.23% [Q1].", "type": "fact", "source_ids": ["Q1"]},
                {"text": "Revenue jumped 99.7%.", "type": "fact", "source_ids": ["M1"]},
                {"text": "Bogus citation.", "type": "fact", "source_ids": ["Z9"]},
            ]}
            out = {k: sec for k in schema["required"] if k != "data_limitations"}
            out["data_limitations"] = []
        else:
            out = {"answer": "AAPL is up 1.23% [Q1] [X5].", "key_points": [], "limitations": [], "suggested_followups": ["What about risks?"]}
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "thinking", "thought": True}, {"text": json.dumps(out)}]}}]})
    return httpx.Response(500)


@pytest.fixture
def client(monkeypatch):
    s = get_settings()
    for k, v in {"finnhub_api_key": "fh-test", "tiingo_api_key": "tg-test", "newsapi_key": "na-test", "gemini_api_key": "gm-test"}.items():
        monkeypatch.setattr(s, k, v)
    mock = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(http_mod, "client", lambda: mock)
    cache.clear_memory_cache()
    from app.database import SessionLocal, init_db
    from app.models import CacheEntry
    init_db()
    with SessionLocal() as db:
        db.query(CacheEntry).delete()
        db.commit()
    with TestClient(app) as c:
        yield c
    cache.clear_memory_cache()


def test_stock_detail_parsing(client):
    r = client.get("/api/stocks/AAPL").json()
    q = r["quote"]["data"]
    assert q["price"] == 231.45 and q["market_time"] == "2025-11-24T21:00:00+00:00"
    assert r["profile"]["data"]["market_cap"] == pytest.approx(3.45e12)
    assert r["metrics"]["data"]["avg_volume_10d"] == pytest.approx(52.5e6)
    assert r["quote"]["meta"]["source"] == "Finnhub" and r["quote"]["meta"]["stale"] is False


def test_unknown_symbol_404(client):
    r = client.get("/api/watchlist")
    assert client.post("/api/watchlist", json={"symbol": "NOPE"}).status_code == 404


def test_search_filters_foreign_listings(client):
    r = client.get("/api/stocks/search?q=apple").json()
    assert [x["symbol"] for x in r["data"]] == ["AAPL"]


def test_history_and_technicals(client):
    r = client.get("/api/stocks/AAPL/history?range=3M").json()
    assert r["provider"] == "Tiingo" and r["adjusted"] is True
    assert 90 <= len(r["bars"]) <= 94  # mock bars are calendar-daily; 3M = 92 days
    assert r["bars"][-1]["sma50"] is not None
    t = client.get("/api/stocks/AAPL/technicals").json()
    assert t["summary"]["rsi14"] == pytest.approx(100.0)  # monotonic rising series
    assert client.get("/api/stocks/ZZZZ/history").status_code == 404


def test_news_merges_and_drops_removed(client):
    r = client.get("/api/news/company/AAPL").json()
    titles = {a["title"] for a in r["articles"]}
    assert titles == {"Apple unveils new chip", "Apple shares rise"}
    assert all(a["id"] for a in r["articles"])


def test_ai_analysis_pipeline_validates_output(client):
    r = client.post("/api/ai/analyze/AAPL?refresh=true")
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    pts = d["sections"]["recent_performance"]["points"]
    assert pts[0]["type"] == "fact"  # numbers match Finnhub quote
    assert pts[1]["type"] == "interpretation" and "unverified_number" in pts[1]["flags"]
    assert pts[2]["source_ids"] == [] and pts[2]["type"] == "interpretation"
    ids = {s["id"] for s in d["sources"]}
    assert {"Q1", "P1", "M1", "T1", "N1"} <= ids
    assert all("data" not in s for s in d["sources"])  # raw context not leaked
    # Context sent to Gemini contained the verified data and the strict rules
    sent = json.dumps(GEMINI_CALLS[-1])
    assert "231.45" in sent and "Never invent" in sent


def test_chat_strips_unknown_inline_citations(client):
    r = client.post("/api/ai/chat", json={"question": "Why is it moving?", "symbol": "AAPL"}).json()
    assert "[Q1]" in r["answer"] and "[X5]" not in r["answer"]
    assert r["suggested_followups"] == ["What about risks?"]


def test_trade_uses_live_quote_timestamp(client):
    client.post("/api/portfolio/reset")
    r = client.post("/api/portfolio/trade", json={"symbol": "AAPL", "side": "BUY", "quantity": 3}).json()
    assert r["transaction"]["price"] == 231.45
    assert r["transaction"]["total"] == pytest.approx(694.35)
    assert r["transaction"]["price_source"] == "Finnhub quote"


# --------------------------------------------------------------------- Gemini fallback

def _gemini_ok(payload):
    return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": json.dumps(payload)}]}}]})


def _run_generate(monkeypatch, responder, chain="primary-model", fallbacks="backup-model"):
    import asyncio
    from app.services import ai
    s = get_settings()
    monkeypatch.setattr(s, "gemini_api_key", "gm-test")
    monkeypatch.setattr(s, "gemini_model", chain)
    monkeypatch.setattr(s, "gemini_fallback_models", fallbacks)
    calls = []

    def h(request):
        model = request.url.path.split("/models/")[1].split(":")[0]
        calls.append(model)
        return responder(model)

    mock = httpx.AsyncClient(transport=httpx.MockTransport(h))
    monkeypatch.setattr(http_mod, "client", lambda: mock)
    return asyncio.run(ai._generate([], {"type": "object"})), calls


def test_gemini_falls_back_when_primary_overloaded(monkeypatch):
    responder = lambda m: httpx.Response(503, json={"error": {"status": "UNAVAILABLE"}}) if m == "primary-model" else _gemini_ok({"ok": True})
    (data, model), calls = _run_generate(monkeypatch, responder)
    assert data == {"ok": True} and model == "backup-model"
    assert calls == ["primary-model", "backup-model"]


def test_gemini_falls_back_on_rate_limit(monkeypatch):
    responder = lambda m: httpx.Response(429) if m == "primary-model" else _gemini_ok({"ok": 1})
    (_, model), _ = _run_generate(monkeypatch, responder)
    assert model == "backup-model"


def test_gemini_permanent_error_does_not_fall_back(monkeypatch):
    from app.core.errors import ProviderError
    with pytest.raises(ProviderError) as ei:
        _run_generate(monkeypatch, lambda m: httpx.Response(400, json={"error": {"message": "bad request"}}))
    assert "HTTP 400" in ei.value.message


def test_gemini_all_models_overloaded_gives_clear_error(monkeypatch):
    from app.core.errors import ProviderError
    with pytest.raises(ProviderError) as ei:
        _run_generate(monkeypatch, lambda m: httpx.Response(503))
    assert ei.value.code == "ai_unavailable"
    assert ei.value.details["models_tried"] == "primary-model, backup-model"


def test_get_json_retries_transient_connection_errors(monkeypatch):
    import asyncio
    calls = {"n": 0}

    def h(request):
        calls["n"] += 1
        if calls["n"] < 3:
            raise httpx.ConnectError("connection reset", request=request)
        return httpx.Response(200, json={"ok": True})

    mock = httpx.AsyncClient(transport=httpx.MockTransport(h))
    monkeypatch.setattr(http_mod, "client", lambda: mock)
    monkeypatch.setattr(http_mod, "_RETRY_DELAYS", (0, 0))
    assert asyncio.run(http_mod.get_json("Finnhub", "https://example.test/x")) == {"ok": True}
    assert calls["n"] == 3


def test_get_json_gives_up_after_retries(monkeypatch):
    import asyncio
    from app.core.errors import ProviderError
    calls = {"n": 0}

    def h(request):
        calls["n"] += 1
        raise httpx.ConnectError("down", request=request)

    mock = httpx.AsyncClient(transport=httpx.MockTransport(h))
    monkeypatch.setattr(http_mod, "client", lambda: mock)
    monkeypatch.setattr(http_mod, "_RETRY_DELAYS", (0, 0))
    with pytest.raises(ProviderError, match="could not be reached"):
        asyncio.run(http_mod.get_json("Finnhub", "https://example.test/x"))
    assert calls["n"] == 3
