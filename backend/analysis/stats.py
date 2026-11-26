"""Statistical associations between observable factors and returns.

IMPORTANT CAVEATS (also written into the report)
* Correlation is not causation. These are descriptive associations over one sample period.
* Many tests are run (targets x tickers x factors). All p-values are adjusted with the
  Benjamini–Hochberg procedure (``p_adj_bh``); only adjusted values should be read as evidence.
* 5-day forward returns from consecutive days overlap, so observations are autocorrelated and
  naive p-values / CIs for ``target_fwd_5d`` are too optimistic.
* Same-day sentiment associations include intraday news that may REACT to the price move.
  ``sentiment_mean_preopen`` (pre-market + overnight news only) is the cleaner same-day test.
"""
from __future__ import annotations

import logging
import math

import numpy as np
import pandas as pd
from scipy import stats as sps

from analysis import config as C

log = logging.getLogger(__name__)

MIN_N = 10
TARGETS = ["target_same_day", "target_next_1d", "target_fwd_5d"]


def _f(x) -> float | None:
    if x is None:
        return None
    x = float(x)
    return None if math.isnan(x) or math.isinf(x) else x


def correlation(x: pd.Series, y: pd.Series) -> dict:
    d = pd.concat([x, y], axis=1).dropna()
    n = len(d)
    if n < MIN_N or d.iloc[:, 0].nunique() < 2 or d.iloc[:, 1].nunique() < 2:
        return {"n": n, "pearson_r": None, "pearson_p": None, "spearman_rho": None, "spearman_p": None}
    pr = sps.pearsonr(d.iloc[:, 0], d.iloc[:, 1])
    sr = sps.spearmanr(d.iloc[:, 0], d.iloc[:, 1])
    return {"n": n, "pearson_r": _f(pr.statistic), "pearson_p": _f(pr.pvalue),
            "spearman_rho": _f(sr.statistic), "spearman_p": _f(sr.pvalue)}


def bootstrap_ci(values: np.ndarray, n_boot: int = 2000, alpha: float = 0.05, seed: int = C.SEED
                 ) -> tuple[float | None, float | None]:
    values = np.asarray(values, dtype=float)
    values = values[~np.isnan(values)]
    if len(values) < 2:
        return None, None
    rng = np.random.default_rng(seed)
    means = rng.choice(values, size=(n_boot, len(values)), replace=True).mean(axis=1)
    return float(np.quantile(means, alpha / 2)), float(np.quantile(means, 1 - alpha / 2))


def group_means(df: pd.DataFrame, group_col: str, target: str, order: list | None = None) -> list[dict]:
    out = []
    groups = order if order is not None else sorted(df[group_col].dropna().unique())
    for gval in groups:
        v = df.loc[df[group_col] == gval, target].dropna().to_numpy()
        lo, hi = bootstrap_ci(v)
        out.append({"group": str(gval), "n": int(len(v)), "mean": _f(v.mean()) if len(v) else None,
                    "ci95_low": lo, "ci95_high": hi})
    return out


def welch(a: np.ndarray, b: np.ndarray) -> float | None:
    a = a[~np.isnan(a)]; b = b[~np.isnan(b)]
    if len(a) < 2 or len(b) < 2:
        return None
    return _f(sps.ttest_ind(a, b, equal_var=False).pvalue)


def kruskal(groups: list[np.ndarray]) -> float | None:
    gs = [g[~np.isnan(g)] for g in groups]
    gs = [g for g in gs if len(g) >= 2]
    if len(gs) < 2:
        return None
    try:
        return _f(sps.kruskal(*gs).pvalue)
    except ValueError:
        return None


def benjamini_hochberg(pvals: list[float]) -> list[float]:
    p = np.asarray(pvals, dtype=float)
    m = len(p)
    if m == 0:
        return []
    order = np.argsort(p)
    ranked = p[order] * m / np.arange(1, m + 1)
    adj = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty(m)
    out[order] = np.minimum(adj, 1.0)
    return out.tolist()


def sentiment_bucket(s: pd.Series) -> pd.Series:
    return pd.Series(np.select([s <= C.SENTIMENT_NEG_THRESHOLD, s >= C.SENTIMENT_POS_THRESHOLD],
                               ["negative", "positive"], "neutral"), index=s.index).where(s.notna())


def add_factor_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Discrete factor labels using FIXED thresholds (no sample-dependent cut-offs -> no look-ahead)."""
    df = df.copy()
    df["sentiment_bucket"] = sentiment_bucket(df["sentiment_mean"])
    df["rsi_zone"] = pd.cut(df["rsi14"], [-np.inf, 30, 70, np.inf], labels=["oversold<30", "neutral30-70", "overbought>70"],
                            right=False).astype("string")
    df["sma200_position"] = np.where(df["px_sma200"].isna(), None,
                                     np.where(df["px_sma200"] > 0, "above_sma200", "below_sma200"))
    df["vol_regime"] = pd.cut(df["vol30"], [-np.inf, 0.20, 0.35, 0.55, np.inf],
                              labels=["low<20%", "moderate20-35%", "high35-55%", "very_high>55%"]).astype("string")
    df["volume_spike"] = np.where(df["volume_z"].isna(), None, np.where(df["volume_z"] > 2, "spike_z>2", "normal"))
    return df


FACTORS = {
    "rsi_zone": ["oversold<30", "neutral30-70", "overbought>70"],
    "sma200_position": ["below_sma200", "above_sma200"],
    "vol_regime": ["low<20%", "moderate20-35%", "high35-55%", "very_high>55%"],
    "volume_spike": ["normal", "spike_z>2"],
}


def run_stats(features: pd.DataFrame) -> dict:
    df = add_factor_columns(features)
    tests: list[dict] = []  # every p-value goes here for BH adjustment

    # --- sentiment vs returns (pooled + per ticker) -------------------------------------
    corr_rows = []
    news_days = df[df["sentiment_mean"].notna()]
    scopes = [("POOLED", news_days)] + [(t, g) for t, g in news_days.groupby("ticker")]
    for scope, g in scopes:
        for target in TARGETS:
            for feat in ("sentiment_mean", "sentiment_mean_preopen") if target == "target_same_day" else ("sentiment_mean",):
                r = correlation(g[feat], g[target])
                row = {"scope": scope, "feature": feat, "target": target, **r}
                corr_rows.append(row)
                for k in ("pearson_p", "spearman_p"):
                    if r[k] is not None:
                        tests.append({"ref": row, "key": k})

    bucket_rows = []
    for target in TARGETS:
        gm = group_means(news_days, "sentiment_bucket", target, ["negative", "neutral", "positive"])
        a = news_days.loc[news_days["sentiment_bucket"] == "positive", target].to_numpy(dtype=float)
        b = news_days.loc[news_days["sentiment_bucket"] == "negative", target].to_numpy(dtype=float)
        row = {"target": target, "groups": gm, "welch_p_pos_vs_neg": welch(a, b)}
        bucket_rows.append(row)
        if row["welch_p_pos_vs_neg"] is not None:
            tests.append({"ref": row, "key": "welch_p_pos_vs_neg"})

    # news volume (has news vs not) vs next-day absolute return: does news coincide with bigger moves?
    df["abs_next_1d"] = df["target_next_1d"].abs()
    news_flag = {"groups": group_means(df.assign(has_news_s=df["has_news"].map({0: "no_news", 1: "has_news"})),
                                       "has_news_s", "abs_next_1d", ["no_news", "has_news"]),
                 "welch_p": welch(df.loc[df["has_news"] == 1, "abs_next_1d"].to_numpy(dtype=float),
                                  df.loc[df["has_news"] == 0, "abs_next_1d"].to_numpy(dtype=float))}
    if news_flag["welch_p"] is not None:
        tests.append({"ref": news_flag, "key": "welch_p"})

    # --- technical factors vs forward 5-day return --------------------------------------
    tech_rows = []
    for factor, order in FACTORS.items():
        for scope, g in [("POOLED", df)] + [(t, gg) for t, gg in df.groupby("ticker")]:
            gm = group_means(g, factor, "target_fwd_5d", order)
            arrays = [g.loc[g[factor] == lv, "target_fwd_5d"].to_numpy(dtype=float) for lv in order]
            row = {"factor": factor, "scope": scope, "target": "target_fwd_5d", "groups": gm,
                   "kruskal_p": kruskal(arrays)}
            tech_rows.append(row)
            if row["kruskal_p"] is not None:
                tests.append({"ref": row, "key": "kruskal_p"})

    # --- Benjamini–Hochberg across ALL tests above --------------------------------------
    adj = benjamini_hochberg([t["ref"][t["key"]] for t in tests])
    for t, p in zip(tests, adj):
        t["ref"][t["key"] + "_adj_bh"] = p
    n_sig = sum(1 for p in adj if p < 0.05)

    return {
        "sentiment_correlations": corr_rows,
        "sentiment_buckets": bucket_rows,
        "news_presence_vs_abs_next_day_move": news_flag,
        "technical_factors_vs_fwd5d": tech_rows,
        "n_tests": len(tests),
        "n_significant_after_bh_0_05": n_sig,
        "n_days_with_news": int(len(news_days)),
        "thresholds": {"sentiment_neg": C.SENTIMENT_NEG_THRESHOLD, "sentiment_pos": C.SENTIMENT_POS_THRESHOLD,
                       "rsi": [30, 70], "vol30_annualised": [0.20, 0.35, 0.55], "volume_spike_z": 2},
        "caveats": [
            "Correlation is not causation; associations are descriptive for this sample only.",
            "p-values adjusted with Benjamini-Hochberg across all tests in this run (*_adj_bh).",
            "5-day forward returns overlap day to day; their p-values/CIs are optimistic.",
            "Same-day sentiment includes intraday news that may react to the price move; "
            "sentiment_mean_preopen excludes it.",
        ],
    }
