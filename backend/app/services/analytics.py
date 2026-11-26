"""Analytics service: all numerical calculations happen here, programmatically,
from real historical data. The AI layer never computes these values."""
from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np

TRADING_DAYS = 252


def _arr(values: Sequence[float]) -> np.ndarray:
    return np.asarray(values, dtype=float)


def sma(values: Sequence[float], window: int) -> list[float | None]:
    """Simple moving average; ``None`` until enough observations exist."""
    a = _arr(values)
    out: list[float | None] = [None] * len(a)
    if window <= 0 or len(a) < window:
        return out
    csum = np.cumsum(np.insert(a, 0, 0.0))
    for i in range(window - 1, len(a)):
        out[i] = float((csum[i + 1] - csum[i + 1 - window]) / window)
    return out


def rsi(closes: Sequence[float], period: int = 14) -> list[float | None]:
    """Relative Strength Index using Wilder's smoothing."""
    a = _arr(closes)
    out: list[float | None] = [None] * len(a)
    if len(a) <= period:
        return out
    deltas = np.diff(a)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = gains[:period].mean()
    avg_loss = losses[:period].mean()

    def _val(g: float, lo: float) -> float:
        if lo == 0:
            return 100.0 if g > 0 else 50.0
        return 100.0 - 100.0 / (1.0 + g / lo)

    out[period] = _val(avg_gain, avg_loss)
    for i in range(period + 1, len(a)):
        avg_gain = (avg_gain * (period - 1) + gains[i - 1]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i - 1]) / period
        out[i] = _val(avg_gain, avg_loss)
    return out


def daily_returns(closes: Sequence[float]) -> list[float]:
    a = _arr(closes)
    if len(a) < 2:
        return []
    return list((a[1:] / a[:-1]) - 1.0)


def log_returns(closes: Sequence[float]) -> np.ndarray:
    a = _arr(closes)
    if len(a) < 2:
        return np.array([])
    return np.log(a[1:] / a[:-1])


def historical_volatility(closes: Sequence[float], window: int = 30) -> float | None:
    """Annualized standard deviation of daily log returns over the last ``window`` days."""
    lr = log_returns(closes)
    if len(lr) < window or window < 2:
        return None
    sample = lr[-window:]
    return float(np.std(sample, ddof=1) * math.sqrt(TRADING_DAYS))


def rolling_volatility(closes: Sequence[float], window: int = 30) -> list[float | None]:
    lr = log_returns(closes)
    out: list[float | None] = [None] * len(closes)
    for i in range(window, len(lr) + 1):
        out[i] = float(np.std(lr[i - window : i], ddof=1) * math.sqrt(TRADING_DAYS))
    return out


def pct_change(first: float, last: float) -> float | None:
    if first in (0, None) or last is None:
        return None
    return (last / first - 1.0) * 100.0


def max_drawdown(closes: Sequence[float]) -> float | None:
    a = _arr(closes)
    if len(a) < 2:
        return None
    peaks = np.maximum.accumulate(a)
    dd = a / peaks - 1.0
    return float(dd.min() * 100.0)


def rsi_label(value: float | None) -> str:
    if value is None:
        return "Not enough data"
    if value >= 70:
        return "Overbought zone (≥70)"
    if value <= 30:
        return "Oversold zone (≤30)"
    return "Neutral range (30–70)"


def volatility_label(ann_vol: float | None) -> str:
    if ann_vol is None:
        return "Not enough data"
    if ann_vol < 0.20:
        return "Low compared with typical stocks"
    if ann_vol < 0.35:
        return "Moderate"
    if ann_vol < 0.55:
        return "High"
    return "Very high"


def technical_summary(dates: Sequence[str], closes: Sequence[float], volumes: Sequence[float]) -> dict:
    """Compute the technical indicator panel from daily bars (oldest first)."""
    n = len(closes)
    sma50 = sma(closes, 50)
    sma200 = sma(closes, 200)
    rsi14 = rsi(closes, 14)
    vol30 = historical_volatility(closes, 30)
    last_close = float(closes[-1]) if n else None
    last_rsi = rsi14[-1] if n else None
    last50 = sma50[-1] if n else None
    last200 = sma200[-1] if n else None

    avg_vol_30 = float(np.mean(volumes[-30:])) if len(volumes) >= 30 else None
    last_volume = float(volumes[-1]) if len(volumes) else None
    vol_ratio = (last_volume / avg_vol_30) if (avg_vol_30 and last_volume is not None) else None

    trend = None
    if last50 is not None and last200 is not None:
        trend = "50-day average is above the 200-day average" if last50 > last200 else "50-day average is below the 200-day average"

    returns = {}
    for label, days in (("1M", 21), ("3M", 63), ("6M", 126), ("1Y", 252)):
        if n > days:
            returns[label] = pct_change(closes[-days - 1], closes[-1])
        else:
            returns[label] = None

    return {
        "as_of": dates[-1] if n else None,
        "observations": n,
        "last_close": last_close,
        "sma50": last50,
        "sma200": last200,
        "price_vs_sma50_pct": pct_change(last50, last_close) if last50 else None,
        "price_vs_sma200_pct": pct_change(last200, last_close) if last200 else None,
        "trend_signal": trend,
        "rsi14": last_rsi,
        "rsi_label": rsi_label(last_rsi),
        "volatility_30d_annualized": vol30,
        "volatility_label": volatility_label(vol30),
        "last_volume": last_volume,
        "avg_volume_30d": avg_vol_30,
        "volume_vs_avg_ratio": vol_ratio,
        "returns_pct": returns,
        "max_drawdown_1y_pct": max_drawdown(closes[-253:]) if n > 20 else None,
        "series": {
            "sma50": sma50,
            "sma200": sma200,
            "rsi14": rsi14,
        },
    }
