"""Tests for the analysis/ research pipeline.

ALL DATA IN THIS FILE IS SYNTHETIC (random walks and template headlines generated here).
It exists only to verify pipeline logic offline; it is never written to analysis/output.
"""
from __future__ import annotations

import json
from datetime import date

import numpy as np
import pandas as pd
import pytest

from analysis import clean, config as C, data_card, features, models, sentiment, stats
from analysis import run_pipeline

ET = "America/New_York"


# ---------------------------------------------------------------- synthetic fixtures (SYNTHETIC) ---

def synthetic_raw_prices(tickers=("AAA", "BBB", "CCC"), start="2023-01-02", end="2024-12-31",
                         holidays=("2024-07-04",), seed=0) -> pd.DataFrame:
    """SYNTHETIC Tiingo-shaped rows (random-walk prices). For tests only."""
    rng = np.random.default_rng(seed)
    days = pd.bdate_range(start, end)
    days = days[~days.isin(pd.to_datetime(list(holidays)))]
    rows = []
    for t in tickers:
        px = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.015, len(days))))
        for d, c in zip(days, px):
            o = c * (1 + rng.normal(0, 0.003))
            hi, lo = max(o, c) * 1.01, min(o, c) * 0.99
            vol = float(rng.integers(1_000_000, 5_000_000))
            rows.append({"ticker": t.lower(), "date": d.strftime("%Y-%m-%dT00:00:00.000Z"), "open": o, "high": hi,
                         "low": lo, "close": c, "volume": vol, "adjOpen": o, "adjHigh": hi, "adjLow": lo,
                         "adjClose": c, "adjVolume": vol, "divCash": 0.0, "splitFactor": 1.0})
    return pd.DataFrame(rows)


HEADLINES = ["{t} beats estimates as revenue surges", "{t} shares fall after weak guidance",
             "{t} announces product event", "{t} faces lawsuit over patents", "{t} upgraded by analysts",
             "{t} stock slumps on demand concerns", "{t} holds annual meeting"]


def synthetic_raw_news(tickers=("AAA", "BBB", "CCC"), start="2024-01-01", end="2024-12-31", per_day=1.2, seed=1):
    """SYNTHETIC Finnhub-shaped articles at random times. For tests only."""
    rng = np.random.default_rng(seed)
    rows, i = [], 0
    for d in pd.date_range(start, end):
        for t in tickers:
            for _ in range(rng.poisson(per_day)):
                ts = pd.Timestamp(d, tz=ET) + pd.Timedelta(minutes=int(rng.integers(0, 24 * 60)))
                rows.append({"ticker": t, "source_api": "finnhub", "id": str(i), "datetime": int(ts.timestamp()),
                             "headline": HEADLINES[int(rng.integers(len(HEADLINES)))].format(t=t),
                             "summary": "", "source": "synthetic", "url": f"https://example.test/{i}",
                             "category": "company", "related": t})
                i += 1
    return pd.DataFrame(rows)


def et_epoch(s: str) -> int:
    return int(pd.Timestamp(s, tz=ET).timestamp())


# ------------------------------------------------------------------------------------ cleaning ---

def test_clean_prices_removes_duplicates_and_invalid_rows():
    raw = synthetic_raw_prices(tickers=("AAA",), start="2024-01-02", end="2024-01-31")
    n = len(raw)
    dup = raw.iloc[[3]].copy()
    bad_hl = raw.iloc[[5]].copy(); bad_hl["date"] = "2024-02-01T00:00:00.000Z"; bad_hl["high"] = bad_hl["low"] * 0.5
    neg = raw.iloc[[6]].copy(); neg["date"] = "2024-02-02T00:00:00.000Z"; neg["close"] = -1.0
    miss = raw.iloc[[7]].copy(); miss["date"] = "2024-02-05T00:00:00.000Z"; miss["close"] = np.nan
    novol = raw.iloc[[8]].copy(); novol["date"] = "2024-02-06T00:00:00.000Z"; novol["volume"] = np.nan
    df, rep = clean.clean_prices(pd.concat([raw, dup, bad_hl, neg, miss, novol], ignore_index=True))
    assert len(df) == n
    assert rep["duplicates_found"] == 1 and rep["duplicates_removed"] == 1
    assert rep["validation_violations"] == 2
    assert not df.duplicated(["ticker", "date"]).any()
    assert (df["ticker"] == "AAA").all()  # upper-cased
    assert df["date"].is_monotonic_increasing and df["date"].dt.tz is None


def test_clean_news_dedupes_by_id_url_and_headline_and_converts_tz():
    base = {"ticker": "aaa", "source_api": "finnhub", "summary": "", "source": "s", "category": "c", "related": "AAA"}
    raw = pd.DataFrame([
        {**base, "id": 1, "datetime": et_epoch("2024-03-01 08:00"), "headline": "AAA beats", "url": "u1"},
        {**base, "id": 1, "datetime": et_epoch("2024-03-01 08:00"), "headline": "AAA beats", "url": "u1"},   # same id
        {**base, "id": 2, "datetime": et_epoch("2024-03-01 09:00"), "headline": "Other", "url": "u1"},       # same url
        {**base, "id": 3, "datetime": et_epoch("2024-03-01 10:00"), "headline": "aaa  BEATS!", "url": "u3"}, # same headline
        {**base, "id": 4, "datetime": et_epoch("2024-03-01 11:00"), "headline": None, "url": "u4"},          # no headline
        {**base, "id": 5, "datetime": et_epoch("2024-03-02 11:00"), "headline": "AAA new", "url": "u5"},
    ])
    df, rep = clean.clean_news(raw)
    assert sorted(df["article_id"]) == ["1", "5"]
    assert rep["duplicates_removed"] == 3
    assert str(df["published_et"].dt.tz) == ET
    assert df.loc[df["article_id"] == "1", "published_et"].iloc[0].hour == 8


# ---------------------------------------------------------------------------- session alignment ---

def test_session_alignment_rules():
    # Calendar: Wed 2024-07-03, (Thu 07-04 holiday), Fri 07-05, Mon 07-08
    cal = pd.DatetimeIndex(["2024-07-03", "2024-07-05", "2024-07-08"])
    cases = {
        "2024-07-03 08:15": ("2024-07-03", "pre_market"),
        "2024-07-03 09:29": ("2024-07-03", "pre_market"),
        "2024-07-03 09:30": ("2024-07-03", "intraday"),
        "2024-07-03 15:59": ("2024-07-03", "intraday"),
        "2024-07-03 16:00": ("2024-07-05", "after_close"),   # skips the holiday
        "2024-07-04 10:00": ("2024-07-05", "non_trading_day"),  # holiday
        "2024-07-05 17:30": ("2024-07-08", "after_close"),   # Friday evening -> Monday
        "2024-07-06 12:00": ("2024-07-08", "non_trading_day"),  # Saturday
        "2024-07-07 23:59": ("2024-07-08", "non_trading_day"),  # Sunday night
        "2024-07-08 16:30": (None, "after_close"),            # beyond calendar -> unassigned
    }
    news = pd.DataFrame({"published_et": [pd.Timestamp(k, tz=ET) for k in cases]})
    # UTC input must give the same answer (2024-07-03 12:15 UTC == 08:15 EDT)
    out = features.assign_sessions(news, cal)
    for (k, (exp_date, exp_timing)), (_, row) in zip(cases.items(), out.iterrows()):
        assert row["session_timing"] == exp_timing, k
        if exp_date is None:
            assert pd.isna(row["session_date"]), k
        else:
            assert row["session_date"] == pd.Timestamp(exp_date), k
    utc = pd.DataFrame({"published_et": [pd.Timestamp("2024-07-03 12:15", tz="UTC")]})
    assert features.assign_sessions(utc, cal)["session_timing"].iloc[0] == "pre_market"


# ------------------------------------------------------------------------ no look-ahead targets ---

def test_forward_returns_and_no_lookahead_in_features():
    prices, _ = clean.clean_prices(synthetic_raw_prices(tickers=("AAA",), start="2023-01-02", end="2024-03-29"))
    f = features.add_price_features(prices).reset_index(drop=True)
    c = f["adj_close"].to_numpy()
    t = 250
    assert f.loc[t, "target_next_1d"] == pytest.approx(c[t + 1] / c[t] - 1)
    assert f.loc[t, "target_fwd_5d"] == pytest.approx(c[t + 5] / c[t] - 1)
    assert f.loc[t, "target_same_day"] == pytest.approx(c[t] / c[t - 1] - 1)
    assert np.isnan(f["target_next_1d"].iloc[-1]) and f["target_fwd_5d"].iloc[-5:].isna().all()

    # Perturb every FUTURE price (and volume) after t: features at <= t must not change.
    p2 = prices.copy()
    future = p2["date"] > f.loc[t, "date"]
    p2.loc[future, ["adj_close", "close", "adj_volume"]] *= 3.0
    f2 = features.add_price_features(p2).reset_index(drop=True)
    cols = features.PRICE_FEATURES + ["sma20", "sma50", "sma200"]
    pd.testing.assert_frame_equal(f.loc[:t, cols], f2.loc[:t, cols])
    assert f.loc[t, "target_next_1d"] != pytest.approx(f2.loc[t, "target_next_1d"])  # target does look forward


# --------------------------------------------------------------------------- chronological split ---

def test_chronological_split_ordered_disjoint_with_embargo():
    dates = pd.Series(np.repeat(pd.bdate_range("2024-01-01", periods=100), 3))
    m = models.chronological_split(dates, embargo=5)
    tr, va, te = (set(dates[m[k]]) for k in ("train", "val", "test"))
    assert tr and va and te
    assert not (tr & va) and not (va & te) and not (tr & te)
    assert max(tr) < min(va) and max(va) < min(te)
    uniq = sorted(dates.unique())
    # embargo: 5 sessions between end of train and start of val
    assert uniq.index(min(va)) - uniq.index(max(tr)) == 6
    m0 = models.chronological_split(dates, embargo=0)
    assert m0["train"].sum() + m0["val"].sum() + m0["test"].sum() == len(dates)


# ------------------------------------------------------------------------------------ data card ---

def test_data_card_fields_present(tmp_path):
    df, rep = clean.clean_prices(synthetic_raw_prices(tickers=("AAA",), start="2024-01-02", end="2024-02-28"))
    card = data_card.build_card(df, name="prices", source="SYNTHETIC test data", source_url="n/a",
                                retrieval_date="2024-03-01", duplicates_found=rep["duplicates_found"],
                                duplicates_removed=rep["duplicates_removed"], date_col="date",
                                important_columns=data_card.PRICE_COLUMNS_DOC)
    for k in data_card.REQUIRED_FIELDS:
        assert k in card, k
    assert card["rows"] == len(df) and card["date_range"]["start"].startswith("2024-01-02")
    data_card.write_cards({"prices": card}, tmp_path)
    assert "prices" in json.loads((tmp_path / "data_card.json").read_text())
    assert "## prices" in (tmp_path / "data_card.md").read_text()


# ------------------------------------------------------------------------------------ sentiment ---

def test_lexicon_sentiment_is_sensible_and_deterministic():
    assert sentiment.lexicon_score("Apple beats estimates, shares surge to record")[0] == "positive"
    assert sentiment.lexicon_score("Tesla shares plunge after recall and lawsuit")[0] == "negative"
    assert sentiment.lexicon_score("Microsoft to hold annual shareholder meeting") == ("neutral", 0.0)
    assert sentiment.lexicon_score("Company did not miss estimates")[1] > 0   # negation flips
    assert sentiment.lexicon_score("X beats") == sentiment.lexicon_score("X beats")
    df = pd.DataFrame({"ticker": ["A"], "article_id": ["1"], "headline": ["A beats"], "summary": [""]})
    out = sentiment.score_news(df, use_llm=False)
    assert out["sentiment_method"].iloc[0] == sentiment.LEXICON_METHOD
    # use_llm=True without a key must still fall back, not fail
    out2 = sentiment.score_news(df, use_llm=True, api_key="", model="m")
    assert out2["sentiment_method"].iloc[0] == sentiment.LEXICON_METHOD


def test_benjamini_hochberg_matches_known_values():
    adj = stats.benjamini_hochberg([0.01, 0.04, 0.03, 0.20])
    assert adj == pytest.approx([0.04, 0.0533333, 0.0533333, 0.20], rel=1e-4)


# ---------------------------------------------------------------------------------- end to end ---

def _synthetic_inputs():
    prices, _ = clean.clean_prices(synthetic_raw_prices())
    news, _ = clean.clean_news(synthetic_raw_news())
    return prices, sentiment.score_news(news, use_llm=False)


def _cfg(tmp_path):
    return C.PipelineConfig(tickers=["AAA", "BBB", "CCC"], days=300, warmup_days=500, end_date=date(2024, 12, 31),
                            use_llm=False, offline=True, output_dir=tmp_path)


def test_end_to_end_stages_on_synthetic_data_lstm_skipped(tmp_path):
    prices, news = _synthetic_inputs()
    cfg = _cfg(tmp_path); cfg.ensure_dirs()
    res = run_pipeline.run_analysis_stages(prices, news, cfg=cfg, cards={}, notes=["SYNTHETIC TEST DATA"])
    for k in ("generated_at", "tickers", "date_range", "data_cards", "stats", "models", "notes"):
        assert k in res
    assert res["models"]["lstm"]["skipped"] is True
    for name in ("naive_zero", "historical_mean", "ridge"):
        assert res["models"][name]["rmse"] is not None
    assert (tmp_path / "report.md").exists() and (tmp_path / "results.json").exists()
    assert (tmp_path / "data_card.md").exists() and any((tmp_path / "figures").glob("*.png"))
    assert res["stats"]["n_tests"] > 0
    assert res["stats"]["n_days_with_news"] > 100  # news actually merged onto trading sessions
    pooled = [r for r in res["stats"]["sentiment_correlations"] if r["scope"] == "POOLED"]
    assert all(r["pearson_r"] is not None for r in pooled)
    json.loads((tmp_path / "results.json").read_text())


def test_forced_tiny_lstm_runs(tmp_path):
    prices, news = _synthetic_inputs()
    cfg = _cfg(tmp_path)
    feats, _ = features.build_feature_table(prices, news, cfg.news_start, cfg.news_end)
    out = models.run_models(feats, target="target_next_1d", force_lstm=True, lstm_max_epochs=2)
    lstm = out["models"]["lstm"]
    assert "skipped" not in lstm and lstm["epochs_run"] <= 2 and np.isfinite(lstm["rmse"])
    out2 = models.run_models(feats, target="target_next_1d", force_lstm=True, lstm_max_epochs=2)
    assert out2["models"]["lstm"]["rmse"] == pytest.approx(lstm["rmse"])  # seeded -> reproducible


# ------------------------------------------------------- collection (mocked HTTP, SYNTHETIC JSON) ---

def test_collect_parses_caches_and_reuses_offline(monkeypatch, tmp_path):
    import httpx

    from analysis import collect

    monkeypatch.setattr(collect, "TIINGO_LIMITER", collect.RateLimiter(0))
    monkeypatch.setattr(collect, "FINNHUB_LIMITER", collect.RateLimiter(0))
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.host)
        if "tiingo" in request.url.host:
            assert request.headers["Authorization"] == "Token tk"
            return httpx.Response(200, json=[{"date": "2024-03-01T00:00:00.000Z", "open": 1, "high": 2, "low": 0.5,
                                              "close": 1.5, "volume": 10, "adjClose": 1.5, "adjVolume": 10}])
        assert request.headers["X-Finnhub-Token"] == "fk"
        return httpx.Response(200, json=[{"category": "company", "datetime": et_epoch("2024-03-01 08:00"),
                                          "headline": "SYNTHETIC beats", "id": 7, "image": "", "related": "AAA",
                                          "source": "s", "summary": "", "url": "https://example.test/7"}])

    client = httpx.Client(transport=httpx.MockTransport(handler))
    cfg = C.PipelineConfig(tickers=["AAA"], days=40, warmup_days=10, end_date=date(2024, 3, 20),
                           output_dir=tmp_path, use_newsapi=False)
    cfg.ensure_dirs()
    monkeypatch.setattr(collect.httpx, "Client", lambda *a, **k: client)
    prices, news = collect.collect_all(cfg, {"tiingo": "tk", "finnhub": "fk"})
    assert len(prices) == 1 and prices["ticker"].iloc[0] == "AAA"
    assert len(news) == 2 and set(news["source_api"]) == {"finnhub"}  # one per monthly chunk (Feb, Mar)
    assert "prices_AAA_" in "".join(collect.load_retrieval_log(cfg.raw_dir))
    n_calls = len(calls)
    cfg.offline = True
    p2, n2 = collect.collect_all(cfg, {})
    assert len(calls) == n_calls and len(p2) == 1 and len(n2) == 2  # served from cache, no HTTP


# ---------------------------------------------------------------------------- missing keys path ---

def test_pipeline_exits_2_with_helpful_message_when_keys_missing(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(run_pipeline, "load_keys", lambda: {"tiingo": "", "finnhub": "", "gemini": "",
                                                            "newsapi": "", "gemini_model": "x"})
    rc = run_pipeline.main(["--output-dir", str(tmp_path)])
    assert rc == 2
    err = capsys.readouterr().err
    assert "TIINGO_API_KEY" in err and "FINNHUB_API_KEY" in err and "backend/.env" in err


def test_offline_without_cache_exits_2(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(run_pipeline, "load_keys", lambda: {"tiingo": "", "finnhub": "", "gemini": "",
                                                            "newsapi": "", "gemini_model": "x"})
    assert run_pipeline.main(["--offline", "--output-dir", str(tmp_path), "--tickers", "AAA"]) == 2
