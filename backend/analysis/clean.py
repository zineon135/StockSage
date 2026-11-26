"""Cleaning and validation of raw price and news data.

Missing-value strategy (documented, deliberately conservative)
---------------------------------------------------------------
Prices
* Rows with missing ``close`` or ``adj_close`` are DROPPED (a return cannot be computed honestly).
* Prices are NEVER forward-filled: a filled price would create artificial zero returns.
* Rows with missing volume are DROPPED (volume features would otherwise be undefined).
* Other OHLC NaNs: the row is dropped by validation (high/low checks need them).
News
* Articles without a headline or a publication timestamp are DROPPED.
* A missing summary becomes an empty string (it is optional text for sentiment scoring).

Duplicates
* Prices: by (ticker, date) — the last retrieved row is kept.
* News: by (ticker, id), then (ticker, url), then (ticker, ET calendar day, normalized headline) —
  earliest kept.

Validation (violations are logged and dropped): prices > 0, high >= low, high >= max(open, close),
low <= min(open, close), volume >= 0, timestamps after 2000-01-01.

Timestamps: Tiingo ``date`` is the trading date (midnight UTC label) -> stored as a tz-naive
calendar date. Finnhub ``datetime`` is a unix epoch (UTC) -> ``published_utc`` and converted to
``published_et`` (America/New_York) for session alignment.
"""
from __future__ import annotations

import logging
import re

import numpy as np
import pandas as pd

from analysis import config as C

log = logging.getLogger(__name__)

PRICE_RENAME = {
    "adjOpen": "adj_open", "adjHigh": "adj_high", "adjLow": "adj_low", "adjClose": "adj_close",
    "adjVolume": "adj_volume", "divCash": "div_cash", "splitFactor": "split_factor",
}
PRICE_NUMERIC = ["open", "high", "low", "close", "volume", "adj_open", "adj_high", "adj_low", "adj_close",
                 "adj_volume", "div_cash", "split_factor"]


def _step(report: dict, name: str, before: int, after: int) -> None:
    report["steps"].append({"step": name, "rows_removed": int(before - after)})
    if before != after:
        log.info("clean: %s removed %d rows", name, before - after)


def clean_prices(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    report: dict = {"rows_in": int(len(raw)), "steps": []}
    df = raw.rename(columns=PRICE_RENAME).copy()
    df["ticker"] = df["ticker"].astype(str).str.strip().str.upper()
    # Tiingo labels each bar with the trading date at 00:00 UTC; keep it as a plain date.
    df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce").dt.tz_localize(None).dt.normalize()
    for col in PRICE_NUMERIC:
        if col not in df.columns:
            # Unadjusted feeds have no adj_*: fall back to the raw column (documented in data card).
            base = col.replace("adj_", "")
            df[col] = df[base] if col.startswith("adj_") and base in df.columns else np.nan
        df[col] = pd.to_numeric(df[col], errors="coerce")

    n = len(df); df = df.dropna(subset=["date"]); _step(report, "drop_missing_date", n, len(df))
    n = len(df); df = df.dropna(subset=["close", "adj_close"]); _step(report, "drop_missing_close", n, len(df))
    n = len(df); df = df.dropna(subset=["volume"]); _step(report, "drop_missing_volume", n, len(df))

    dup_mask = df.duplicated(subset=["ticker", "date"], keep="last")
    report["duplicates_found"] = int(dup_mask.sum())
    n = len(df); df = df[~dup_mask]; _step(report, "drop_duplicate_ticker_date", n, len(df))
    report["duplicates_removed"] = int(n - len(df))

    valid = (
        (df[["open", "high", "low", "close", "adj_close"]] > 0).all(axis=1)
        & (df["high"] >= df["low"])
        & (df["high"] >= df[["open", "close"]].max(axis=1) - 1e-9)
        & (df["low"] <= df[["open", "close"]].min(axis=1) + 1e-9)
        & (df["volume"] >= 0)
    )
    report["validation_violations"] = int((~valid).sum())
    if (~valid).any():
        log.warning("clean: dropping %d price rows failing validation: %s", int((~valid).sum()),
                    df.loc[~valid, ["ticker", "date"]].head(5).to_dict("records"))
    n = len(df); df = df[valid]; _step(report, "drop_validation_violations", n, len(df))

    if df["adj_volume"].isna().all():
        df["adj_volume"] = df["volume"]
    df["adj_volume"] = df["adj_volume"].fillna(df["volume"])
    df = df.sort_values(["ticker", "date"]).reset_index(drop=True)
    cols = ["ticker", "date"] + PRICE_NUMERIC
    df = df[cols]
    report["rows_out"] = int(len(df))
    return df, report


def normalize_headline(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def clean_news(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    report: dict = {"rows_in": int(len(raw)), "steps": []}
    out_cols = ["ticker", "article_id", "source_api", "published_utc", "published_et", "headline", "summary",
                "source", "url", "category"]
    if raw.empty:
        report.update(duplicates_found=0, duplicates_removed=0, validation_violations=0, rows_out=0)
        return pd.DataFrame(columns=out_cols), report
    df = raw.reset_index(drop=True).copy()
    df["ticker"] = df["ticker"].astype(str).str.strip().str.upper()
    df["article_id"] = df["id"].astype("string").str.replace(r"\.0$", "", regex=True)
    if "source_api" not in df.columns:
        df["source_api"] = "finnhub"
    for col in ("headline", "summary", "source", "url", "category"):
        if col not in df.columns:
            df[col] = pd.NA
        df[col] = df[col].astype("string").str.strip()
    df["summary"] = df["summary"].fillna("")
    ts = pd.to_numeric(df["datetime"], errors="coerce")
    df["published_utc"] = pd.to_datetime(ts, unit="s", utc=True, errors="coerce")

    n = len(df)
    df = df[df["headline"].notna() & (df["headline"] != "") & df["published_utc"].notna()]
    _step(report, "drop_missing_headline_or_time", n, len(df))

    valid = df["published_utc"] >= pd.Timestamp("2000-01-01", tz="UTC")
    report["validation_violations"] = int((~valid).sum())
    n = len(df); df = df[valid]; _step(report, "drop_invalid_timestamp", n, len(df))

    df["published_et"] = df["published_utc"].dt.tz_convert(C.MARKET_TZ)
    df = df.sort_values(["ticker", "published_utc"])  # keep earliest copy of a story
    df["_norm_headline"] = df["headline"].map(normalize_headline)
    # Headline duplicates are only collapsed within the same ticker and ET calendar day (syndicated
    # copies); identical generic titles on different days are distinct stories.
    df["_et_day"] = df["published_et"].dt.strftime("%Y-%m-%d")
    found = 0
    n0 = len(df)
    for keys, name in ((["ticker", "article_id"], "id"), (["ticker", "url"], "url"),
                       (["ticker", "_et_day", "_norm_headline"], "headline")):
        sub = df.dropna(subset=[keys[-1]]) if name != "headline" else df
        mask = sub.duplicated(subset=keys, keep="first")
        found += int(mask.sum())
        n = len(df)
        df = df.drop(index=sub.index[mask])
        _step(report, f"drop_duplicate_by_{name}", n, len(df))
    report["duplicates_found"] = found
    report["duplicates_removed"] = int(n0 - len(df))
    df = df.drop(columns=["_norm_headline", "_et_day"])
    df["article_id"] = df["article_id"].fillna(df["url"]).astype(str)
    df = df[out_cols].sort_values(["ticker", "published_utc"]).reset_index(drop=True)
    report["rows_out"] = int(len(df))
    return df, report
