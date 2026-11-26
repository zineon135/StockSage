"""Feature engineering with an explicit, leakage-safe timing convention.

TIMING CONVENTION (read this before using any column)
=====================================================
Row ``t`` = one ticker on one trading session ``t`` (dates come from the cleaned price data).

Features on row t use only information available by the CLOSE of session t:
* price/volume features use adj_close / adj_volume up to and including t;
* volume z-score compares volume[t] with the mean/std of the PRIOR 20 sessions (t-20..t-1);
* news features aggregate articles ASSIGNED to session t (rules below), all of which were
  published before 16:00 ET on t.

News -> session assignment (publication time converted to America/New_York):
* published on a trading day before 09:30 ET   -> session t = that day   (timing = "pre_market";
  information known at the OPEN of t, so a same-day price reaction is possible)
* published on a trading day 09:30–15:59:59 ET -> session t = that day   (timing = "intraday";
  overlaps the price move -> same-day association is contemporaneous, NOT predictive)
* published on a trading day at/after 16:00 ET -> NEXT trading session   (timing = "after_close")
* published on a weekend / holiday               -> NEXT trading session   (timing = "non_trading_day")
The trading calendar is the set of dates present in the price data (no external holiday list).
Early-close sessions (e.g. 13:00 ET) are treated as 16:00 closes — a known small limitation.

Targets on row t (never used as features):
* ``target_same_day`` = adj_close[t]/adj_close[t-1] - 1   (contemporaneous, association only)
* ``target_next_1d``  = adj_close[t+1]/adj_close[t] - 1   (first return strictly after features are known)
* ``target_fwd_5d``   = adj_close[t+5]/adj_close[t] - 1   (cumulative over sessions t+1..t+5)
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from analysis import config as C
from app.services import analytics

log = logging.getLogger(__name__)

PRICE_FEATURES = ["ret", "log_ret", "ret_lag1", "ret_lag2", "ret_lag3", "ret_lag4", "vol20", "vol30",
                  "px_sma20", "px_sma50", "px_sma200", "rsi14", "volume_change", "volume_z"]
NEWS_FEATURES = ["news_count", "sentiment_mean", "sentiment_mean_preopen", "news_count_intraday", "news_pos_share"]
TARGETS = ["target_same_day", "target_next_1d", "target_fwd_5d"]

_OPEN_MIN = C.MARKET_OPEN[0] * 60 + C.MARKET_OPEN[1]
_CLOSE_MIN = C.MARKET_CLOSE[0] * 60 + C.MARKET_CLOSE[1]


def _none_to_nan(values) -> np.ndarray:
    return np.array([np.nan if v is None else v for v in values], dtype=float)


def _ticker_price_features(g: pd.DataFrame) -> pd.DataFrame:
    g = g.sort_values("date").copy()
    px = g["adj_close"].to_numpy(dtype=float)
    g["ret"] = g["adj_close"].pct_change()
    g["log_ret"] = np.log(g["adj_close"] / g["adj_close"].shift(1))
    for k in range(1, 5):
        g[f"ret_lag{k}"] = g["ret"].shift(k)
    # Volatility and indicators reuse the app's audited implementations.
    g["vol20"] = _none_to_nan(analytics.rolling_volatility(px, 20))
    g["vol30"] = _none_to_nan(analytics.rolling_volatility(px, 30))
    for w in (20, 50, 200):
        g[f"sma{w}"] = _none_to_nan(analytics.sma(px, w))
        g[f"px_sma{w}"] = g["adj_close"] / g[f"sma{w}"] - 1.0
    g["rsi14"] = _none_to_nan(analytics.rsi(px, 14))
    v = g["adj_volume"].astype(float)
    g["volume_change"] = v.pct_change().replace([np.inf, -np.inf], np.nan)
    prior_mean = v.shift(1).rolling(20).mean()
    prior_std = v.shift(1).rolling(20).std()
    g["volume_z"] = ((v - prior_mean) / prior_std.replace(0, np.nan))
    # Targets: shift(-k) looks FORWARD k rows within the ticker; these are labels only.
    g["target_same_day"] = g["ret"]
    g["target_next_1d"] = g["adj_close"].shift(-1) / g["adj_close"] - 1.0
    g["target_fwd_5d"] = g["adj_close"].shift(-5) / g["adj_close"] - 1.0
    return g


def add_price_features(prices: pd.DataFrame) -> pd.DataFrame:
    parts = [_ticker_price_features(g) for _, g in prices.groupby("ticker", sort=True)]
    return pd.concat(parts, ignore_index=True) if parts else prices.copy()


def trading_calendar(prices: pd.DataFrame) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(sorted(pd.to_datetime(prices["date"]).dt.normalize().unique()))


def assign_sessions(news: pd.DataFrame, calendar: pd.DatetimeIndex) -> pd.DataFrame:
    """Add ``session_date`` and ``session_timing`` per the convention in the module docstring."""
    news = news.copy()
    if news.empty:
        news["session_date"] = pd.Series(dtype="datetime64[ns]")
        news["session_timing"] = pd.Series(dtype="object")
        return news
    et = pd.to_datetime(news["published_et"])
    if et.dt.tz is None:
        raise ValueError("published_et must be timezone-aware (America/New_York)")
    et = et.dt.tz_convert(C.MARKET_TZ)
    day = et.dt.tz_localize(None).dt.normalize()
    minutes = et.dt.hour * 60 + et.dt.minute
    cal = calendar.normalize().values.astype("datetime64[ns]")
    day_vals = day.values.astype("datetime64[ns]")
    is_trading = np.isin(day_vals, cal)
    nxt_idx = np.searchsorted(cal, day_vals, side="right")
    nxt = np.array([cal[i] if i < len(cal) else np.datetime64("NaT", "ns") for i in nxt_idx], dtype="datetime64[ns]")

    timing = np.where(~is_trading, "non_trading_day",
                      np.where(minutes < _OPEN_MIN, "pre_market",
                               np.where(minutes < _CLOSE_MIN, "intraday", "after_close")))
    same_day = is_trading & (minutes < _CLOSE_MIN)
    session = np.where(same_day, day_vals, nxt)
    news["session_date"] = pd.to_datetime(session)
    news["session_timing"] = timing
    return news


def aggregate_news_daily(news: pd.DataFrame) -> pd.DataFrame:
    cols = ["ticker", "date"] + NEWS_FEATURES
    if news.empty:
        return pd.DataFrame(columns=cols)
    n = news.dropna(subset=["session_date"]).copy()
    n["date"] = n["session_date"]
    n["is_pos"] = (n["sentiment_label"] == "positive").astype(float)
    n["is_intraday"] = (n["session_timing"] == "intraday").astype(float)
    n["score_preopen"] = n["sentiment_score"].where(n["session_timing"] != "intraday")
    agg = n.groupby(["ticker", "date"]).agg(
        news_count=("sentiment_score", "size"),
        sentiment_mean=("sentiment_score", "mean"),
        sentiment_mean_preopen=("score_preopen", "mean"),
        news_count_intraday=("is_intraday", "sum"),
        news_pos_share=("is_pos", "mean"),
    ).reset_index()
    return agg[cols]


def build_feature_table(prices: pd.DataFrame, news_scored: pd.DataFrame, start=None, end=None
                        ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (features restricted to [start, end], news with session assignment)."""
    feats = add_price_features(prices)
    cal = trading_calendar(prices)
    news_sess = assign_sessions(news_scored, cal)
    dropped = int(news_sess["session_date"].isna().sum()) if len(news_sess) else 0
    if dropped:
        log.info("features: %d articles fall after the last trading date and are dropped", dropped)
    daily = aggregate_news_daily(news_sess)
    out = feats.merge(daily, on=["ticker", "date"], how="left")
    out["news_count"] = out["news_count"].fillna(0).astype(int)
    out["news_count_intraday"] = out["news_count_intraday"].fillna(0).astype(int)
    out["has_news"] = (out["news_count"] > 0).astype(int)
    if start is not None:
        out = out[out["date"] >= pd.Timestamp(start)]
    if end is not None:
        out = out[out["date"] <= pd.Timestamp(end)]
    return out.sort_values(["date", "ticker"]).reset_index(drop=True), news_sess
