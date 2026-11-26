"""Writes output/report.md, output/results.json and figures (matplotlib, Agg backend)."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402


log = logging.getLogger(__name__)

BLUE, ORANGE, GREY, INK, INK2 = "#257de0", "#f47230", "#9c9c9c", "#191919", "#666666"


def _style(ax, title: str, xlabel: str = "", ylabel: str = "") -> None:
    ax.set_title(title, loc="left", fontsize=11, color=INK)
    ax.set_xlabel(xlabel, color=INK2); ax.set_ylabel(ylabel, color=INK2)
    ax.tick_params(colors=INK2, labelsize=8)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("#cccccc")
    ax.grid(axis="y", color="#eeeeee", linewidth=0.8)
    ax.set_axisbelow(True)


def _save(fig, path: Path) -> str:
    fig.tight_layout()
    fig.savefig(path, dpi=120, facecolor="white")
    plt.close(fig)
    return path.name


def _bar_groups(ax, groups: list[dict], scale: float = 100.0) -> None:
    labels = [f"{g['group']}\n(n={g['n']})" for g in groups]
    means = [(g["mean"] or 0) * scale for g in groups]
    lo = [((g["mean"] or 0) - (g["ci95_low"] if g["ci95_low"] is not None else g["mean"] or 0)) * scale for g in groups]
    hi = [((g["ci95_high"] if g["ci95_high"] is not None else g["mean"] or 0) - (g["mean"] or 0)) * scale for g in groups]
    ax.bar(labels, means, color=BLUE, width=0.55, yerr=[lo, hi], ecolor=INK2, capsize=3)
    ax.axhline(0, color=INK2, linewidth=0.8)


def make_figures(features: pd.DataFrame, news: pd.DataFrame, stats: dict, model_results: list[dict],
                 fig_dir: Path) -> list[str]:
    fig_dir.mkdir(parents=True, exist_ok=True)
    out = []
    # 1) sentiment vs next-day return
    d = features.dropna(subset=["sentiment_mean", "target_next_1d"])
    if len(d) >= 3:
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.scatter(d["sentiment_mean"], d["target_next_1d"] * 100, s=10, alpha=0.4, color=BLUE, linewidths=0)
        if d["sentiment_mean"].nunique() > 1:
            k, b = np.polyfit(d["sentiment_mean"], d["target_next_1d"] * 100, 1)
            xs = np.linspace(d["sentiment_mean"].min(), d["sentiment_mean"].max(), 50)
            ax.plot(xs, k * xs + b, color=ORANGE, linewidth=2, label=f"OLS fit (slope {k:.2f})")
            ax.legend(frameon=False, fontsize=8)
        _style(ax, "Daily mean news sentiment vs next-session return", "Mean sentiment (session t)",
               "Return t→t+1 (%)")
        out.append(_save(fig, fig_dir / "sentiment_vs_next_day.png"))
    # 2) sentiment buckets (5-day)
    for row in stats.get("sentiment_buckets", []):
        if row["target"] == "target_fwd_5d" and any(g["n"] for g in row["groups"]):
            fig, ax = plt.subplots(figsize=(6, 4))
            _bar_groups(ax, row["groups"])
            _style(ax, "Mean 5-session forward return by sentiment bucket (95% bootstrap CI)", "", "Return (%)")
            out.append(_save(fig, fig_dir / "sentiment_buckets_fwd5d.png"))
    # 3) technical factors (pooled)
    pooled = [r for r in stats.get("technical_factors_vs_fwd5d", []) if r["scope"] == "POOLED"]
    if pooled:
        fig, axes = plt.subplots(1, len(pooled), figsize=(4 * len(pooled), 4), sharey=True)
        for ax, r in zip(np.atleast_1d(axes), pooled):
            _bar_groups(ax, r["groups"])
            _style(ax, r["factor"], "", "5-session fwd return (%)")
            ax.tick_params(axis="x", labelsize=7)
        out.append(_save(fig, fig_dir / "technical_factors_fwd5d.png"))
    # 4) model comparison
    for mr in model_results:
        rows = [(k, v["rmse"]) for k, v in mr.get("models", {}).items() if "rmse" in v]
        if rows:
            fig, ax = plt.subplots(figsize=(6, 3.5))
            names, vals = zip(*rows)
            colors = [GREY if n == "naive_zero" else BLUE for n in names]
            ax.barh(names, [v * 100 for v in vals], color=colors, height=0.5)
            _style(ax, f"Test RMSE ({mr['target']}) — lower is better", "RMSE (percentage points)")
            ax.grid(axis="x", color="#eeeeee"); ax.grid(axis="y", visible=False)
            out.append(_save(fig, fig_dir / f"model_rmse_{mr['target']}.png"))
    # 5) news volume over time
    if len(news) and "session_date" in news:
        s = news.dropna(subset=["session_date"]).groupby("session_date").size()
        if len(s):
            fig, ax = plt.subplots(figsize=(7, 3))
            ax.plot(s.index, s.values, color=BLUE, linewidth=1.5)
            _style(ax, "Articles per trading session (all tickers)", "", "Articles")
            out.append(_save(fig, fig_dir / "news_volume.png"))
    return out


def _pct(x) -> str:
    return "n/a" if x is None else f"{x * 100:.3f}%"


def _num(x, nd=3) -> str:
    return "n/a" if x is None else f"{x:.{nd}f}"


def write_report(*, out_dir: Path, tickers: list[str], date_range: dict, cards: dict, stats: dict,
                 model_results: list[dict], figures: list[str], notes: list[str], run_args: dict | None = None
                 ) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    primary = next((m for m in model_results if m["target"] == "target_next_1d"), None)
    models_json: dict = {}
    for mr in model_results:
        suffix = "" if mr["target"] == "target_next_1d" else "_5d"
        for name, v in mr.get("models", {}).items():
            models_json[name + suffix] = {k: v.get(k) for k in ("mae", "rmse", "directional_accuracy", "n_test")} \
                if "rmse" in v else {"mae": None, "rmse": None, "directional_accuracy": None,
                                     "skipped": True, "reason": v.get("reason")}
    stats_json = {k: v for k, v in stats.items()}
    results = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tickers": tickers,
        "date_range": date_range,
        "data_cards": cards,
        "stats": stats_json,
        "models": models_json,
        "notes": notes,
        "run_args": run_args or {},
    }
    (out_dir / "results.json").write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")

    L: list[str] = []
    L += ["# Stock Sage research report", "",
          f"_Generated {results['generated_at']} by `python -m analysis.run_pipeline`._", "",
          "> Educational analysis only — not investment advice. Associations are not causal.", "",
          "## Research question", "",
          "Using historical stock market data and financial news, what observable factors are associated with "
          "positive or negative stock performance over a selected period, and how can those factors help identify "
          "potential opportunities and risks?", "",
          "## Data", "",
          f"- Tickers: {', '.join(tickers)}",
          f"- Analysis window: {date_range.get('start')} to {date_range.get('end')} "
          f"(price history starts earlier for indicator warm-up)", ""]
    L += ["| Dataset | Source | Rows | Duplicates removed | Date range |", "|---|---|---|---|---|"]
    for c in cards.values():
        dr = c.get("date_range") or {}
        L.append(f"| {c['dataset_name']} | {c['data_source']} | {c['rows']} | {c['duplicates_removed']} | "
                 f"{dr.get('start', 'n/a')} – {dr.get('end', 'n/a')} |")
    L += ["", "Full data cards: `data_card.md` / `data_card.json`.", ""]
    methods = (cards.get("news", {}).get("notes") or [])
    L += [f"- {m}" for m in methods] + [""]

    L += ["## Methodology and leakage handling", "",
          "- Returns and indicators use split/dividend-adjusted close (`adj_close`). Indicators (SMA, Wilder "
          "RSI14, rolling volatility) reuse `app.services.analytics`.",
          "- **Row t only uses information available by the close of session t.** Volume z-score is relative to "
          "the prior 20 sessions.",
          "- **News → session alignment (America/New_York):** before 09:30 on a trading day → that session "
          "(`pre_market`); 09:30–16:00 → that session, flagged `intraday`; after 16:00 or on a weekend/holiday → "
          "the next trading session in the price calendar. Early closes are treated as 16:00.",
          "- **Targets:** same-day `adj_close[t]/adj_close[t-1]-1` (contemporaneous, association only), next-day "
          "`adj_close[t+1]/adj_close[t]-1`, and 5-day `adj_close[t+5]/adj_close[t]-1`.",
          "- **Models:** chronological 70/15/15 split pooled by date (no shuffling), embargo of h sessions between "
          "splits, scaler fit on train only, baselines before Ridge and LSTM.",
          "- **Statistics:** Pearson/Spearman with p-values, bootstrap 95% CIs for group means, Welch t-tests and "
          "Kruskal–Wallis; all p-values Benjamini–Hochberg adjusted.", ""]

    L += ["## Results: news sentiment vs returns (pooled)", "",
          f"Days (ticker-sessions) with at least one article: {stats.get('n_days_with_news', 0)}.", "",
          "| Feature | Target | n | Pearson r | p (BH) | Spearman ρ | p (BH) |", "|---|---|---|---|---|---|---|"]
    for r in stats.get("sentiment_correlations", []):
        if r["scope"] == "POOLED":
            L.append(f"| {r['feature']} | {r['target']} | {r['n']} | {_num(r['pearson_r'])} | "
                     f"{_num(r.get('pearson_p_adj_bh'))} | {_num(r['spearman_rho'])} | {_num(r.get('spearman_p_adj_bh'))} |")
    L += ["", "| Target | Bucket | n | Mean return | 95% CI | Welch p pos vs neg (BH) |", "|---|---|---|---|---|---|"]
    for b in stats.get("sentiment_buckets", []):
        for g in b["groups"]:
            L.append(f"| {b['target']} | {g['group']} | {g['n']} | {_pct(g['mean'])} | "
                     f"[{_pct(g['ci95_low'])}, {_pct(g['ci95_high'])}] | {_num(b.get('welch_p_pos_vs_neg_adj_bh'))} |")
    L += ["", "Per-ticker correlations are in `results.json` → `stats.sentiment_correlations`.", ""]

    L += ["## Results: technical factors vs 5-session forward return (pooled)", "",
          "| Factor | Group | n | Mean fwd 5d | 95% CI | Kruskal p (BH) |", "|---|---|---|---|---|---|"]
    for r in stats.get("technical_factors_vs_fwd5d", []):
        if r["scope"] == "POOLED":
            for g in r["groups"]:
                L.append(f"| {r['factor']} | {g['group']} | {g['n']} | {_pct(g['mean'])} | "
                         f"[{_pct(g['ci95_low'])}, {_pct(g['ci95_high'])}] | {_num(r.get('kruskal_p_adj_bh'))} |")
    L += ["", f"Tests run: {stats.get('n_tests', 0)}; significant at BH-adjusted 0.05: "
          f"{stats.get('n_significant_after_bh_0_05', 0)}.", ""]

    L += ["## Results: predictive models (test split)", ""]
    for mr in model_results:
        L += [f"### Target `{mr['target']}`", ""]
        if "split" in mr:
            s = mr["split"]
            L.append(f"Split — train {s['train']['start']}..{s['train']['end']} ({s['train']['rows']} rows), "
                     f"val {s['val']['start']}..{s['val']['end']} ({s['val']['rows']}), "
                     f"test {s['test']['start']}..{s['test']['end']} ({s['test']['rows']}); "
                     f"embargo {s['embargo_sessions']} session(s).")
            L.append("")
        L += ["| Model | MAE | RMSE | Directional accuracy |", "|---|---|---|---|"]
        for name, v in mr.get("models", {}).items():
            if "rmse" in v:
                L.append(f"| {name} | {_pct(v['mae'])} | {_pct(v['rmse'])} | {_num(v['directional_accuracy'])} |")
            else:
                L.append(f"| {name} | skipped | — | {v.get('reason', '')} |")
        L += [""] + [f"- {n}" for n in mr.get("notes", [])] + [""]
    if primary is None:
        L += ["No model results.", ""]

    if figures:
        L += ["## Figures", ""] + [f"![{f}](figures/{f})" for f in figures] + [""]

    L += ["## Interpretation guide", "",
          "- A factor is only worth discussing as a potential *opportunity or risk signal* if its association "
          "survives BH adjustment, is consistent across tickers, and holds out of sample. Most will not.",
          "- If no model beats the naive zero-return baseline on test RMSE, that is the expected result for "
          "daily returns and should be reported as such, not hidden.", "",
          "## Limitations", "",
          "- One short period (~1 year of news) and a small, large-cap ticker set: results may not generalise.",
          "- Finnhub's free news feed is incomplete and its coverage varies by ticker and month.",
          "- Lexicon sentiment (when Gemini is unavailable) is crude; LLM sentiment may be inconsistent over time.",
          "- 5-day forward returns overlap, inflating apparent significance; no transaction costs are modelled.",
          "- The trading calendar is inferred from price data; early-close sessions are treated as full days.",
          "- Correlation is not causation; survivorship and selection bias in the ticker list are not addressed.", "",
          "## Run notes", ""] + [f"- {n}" for n in notes] + [""]
    (out_dir / "report.md").write_text("\n".join(L), encoding="utf-8")
    return results


