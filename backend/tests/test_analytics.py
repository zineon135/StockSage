import math

import numpy as np
import pytest

from app.services import analytics as a


def test_sma_basic():
    out = a.sma([1, 2, 3, 4, 5], 3)
    assert out[:2] == [None, None]
    assert out[2:] == pytest.approx([2.0, 3.0, 4.0])


def test_sma_insufficient_data():
    assert a.sma([1, 2], 5) == [None, None]


def test_rsi_all_gains_is_100():
    closes = list(range(1, 30))
    r = a.rsi(closes, 14)
    assert r[13] is None
    assert r[14] == pytest.approx(100.0)


def test_rsi_all_losses_is_0():
    r = a.rsi(list(range(30, 0, -1)), 14)
    assert r[-1] == pytest.approx(0.0)


def test_rsi_known_reference_values():
    # Classic Wilder example (StockCharts "RSI" worksheet).
    closes = [44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84, 46.08, 45.89, 46.03,
              45.61, 46.28, 46.28, 46.00, 46.03, 46.41, 46.22, 45.64]
    # The worksheet rounds intermediate averages, so exact math differs by ~0.07.
    r = a.rsi(closes, 14)
    assert r[14:] == pytest.approx([70.53, 66.32, 66.55, 69.41, 66.36, 57.97], abs=0.1)


def test_volatility_matches_numpy():
    rng = np.random.default_rng(0)
    closes = list(100 * np.exp(np.cumsum(rng.normal(0, 0.01, 100))))
    expected = np.std(np.log(np.array(closes[1:]) / np.array(closes[:-1]))[-30:], ddof=1) * math.sqrt(252)
    assert a.historical_volatility(closes, 30) == pytest.approx(expected)


def test_volatility_none_when_short():
    assert a.historical_volatility([1, 2, 3], 30) is None


def test_pct_change_and_drawdown():
    assert a.pct_change(100, 110) == pytest.approx(10.0)
    assert a.pct_change(0, 5) is None
    assert a.max_drawdown([100, 120, 90, 130]) == pytest.approx(-25.0)


def test_technical_summary_shapes():
    closes = [100 + i * 0.5 for i in range(260)]
    vols = [1_000_000] * 260
    dates = [f"d{i}" for i in range(260)]
    s = a.technical_summary(dates, closes, vols)
    assert s["sma50"] is not None and s["sma200"] is not None
    assert s["trend_signal"].startswith("50-day average is above")
    assert s["volume_vs_avg_ratio"] == pytest.approx(1.0)
    assert s["returns_pct"]["1M"] is not None
