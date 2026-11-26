import asyncio

import pytest

from app.services import ai

CTX = {
    "symbol": "AAPL",
    "company_name": "Apple Inc",
    "generated_at": "2026-11-25T00:00:00Z",
    "unavailable": [],
    "sources": [
        {"id": "Q1", "data": {"price": 231.45, "change_pct": 1.234, "market_time": "2026-11-24T21:00:00Z"}},
        {"id": "P1", "data": {"market_cap": 3.45e12, "name": "Apple Inc"}},
        {"id": "T1", "data": {"rsi14": 61.2, "volatility_30d_annualized": 0.2412}},
    ],
}


def _validate(points):
    ids, known = ai._ctx_index(CTX)
    warnings = []
    return ai._validate_points(points, ids, known, warnings), warnings


def test_fact_with_matching_numbers_stays_fact():
    pts, w = _validate([{"text": "AAPL last traded at $231.45, up 1.23% [Q1].", "type": "fact", "source_ids": ["Q1"]}])
    assert pts[0]["type"] == "fact" and not pts[0]["flags"]


def test_scaled_and_percent_numbers_are_recognized():
    pts, _ = _validate([
        {"text": "Market cap is about $3.45 trillion.", "type": "fact", "source_ids": ["P1"]},
        {"text": "30-day volatility is 24.12% annualized.", "type": "fact", "source_ids": ["T1"]},
    ])
    assert [p["type"] for p in pts] == ["fact", "fact"]


def test_invented_number_is_downgraded():
    pts, w = _validate([{"text": "Revenue grew 47.9% last year.", "type": "fact", "source_ids": ["P1"]}])
    assert pts[0]["type"] == "interpretation"
    assert "unverified_number" in pts[0]["flags"]
    assert any("47.9" in x for x in w)


def test_unknown_citation_removed_and_unsourced_fact_downgraded():
    pts, w = _validate([{"text": "Apple announced a buyback.", "type": "fact", "source_ids": ["N9"]}])
    assert pts[0]["source_ids"] == []
    assert pts[0]["type"] == "interpretation"
    assert "removed_unknown_citation" in pts[0]["flags"]


def test_guarantee_language_flagged():
    pts, _ = _validate([{"text": "This stock is guaranteed to rise.", "type": "interpretation", "source_ids": []}])
    assert "guarantee_language" in pts[0]["flags"]


def test_inline_citations_cleaned():
    assert ai._clean_inline_citations("Up today [Q1, N7] and [X3].", {"Q1"}) == "Up today [Q1] and ."


def test_missing_key_raises_not_configured(monkeypatch):
    from app.config import get_settings
    from app.core.errors import ProviderNotConfigured

    monkeypatch.setattr(get_settings(), "gemini_api_key", "")
    with pytest.raises(ProviderNotConfigured):
        asyncio.run(ai._generate([], {}))
