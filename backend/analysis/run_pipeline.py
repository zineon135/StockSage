"""Run the full research pipeline top to bottom.

    cd backend
    python -m analysis.run_pipeline [--tickers AAPL MSFT] [--days 365] [--no-llm] [--offline]

Exit codes: 0 success, 2 missing API keys / no cached data, 3 data collection failed.
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

import pandas as pd

from analysis import config as C

log = logging.getLogger("analysis")

KEY_HELP = """
Stock Sage research pipeline: required API keys are missing: {missing}

Add them to backend/.env (this file is read by app/config.py; never commit it):

    TIINGO_API_KEY=your_tiingo_key        # daily prices   - free: https://www.tiingo.com/account/api/token
    FINNHUB_API_KEY=your_finnhub_key      # company news   - free: https://finnhub.io/dashboard
    GEMINI_API_KEY=your_gemini_key        # optional: LLM sentiment (otherwise lexicon_v1 fallback)
    NEWSAPI_KEY=your_newsapi_key          # optional: ~1 month supplementary news

Then rerun:  python -m analysis.run_pipeline
Or, if raw CSVs were cached by an earlier online run:  python -m analysis.run_pipeline --offline
"""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="python -m analysis.run_pipeline", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--tickers", nargs="+", default=C.DEFAULT_TICKERS)
    p.add_argument("--days", type=int, default=C.DEFAULT_DAYS, help="analysis window in calendar days")
    p.add_argument("--warmup-days", type=int, default=C.DEFAULT_WARMUP_DAYS)
    p.add_argument("--end-date", type=date.fromisoformat, default=date.today())
    p.add_argument("--no-llm", action="store_true", help="use the lexicon sentiment scorer only")
    p.add_argument("--no-newsapi", action="store_true", help="ignore NEWSAPI_KEY even if set")
    p.add_argument("--offline", action="store_true", help="use cached raw CSVs only (no network)")
    p.add_argument("--output-dir", type=Path, default=C.OUTPUT_DIR)
    p.add_argument("--seed", type=int, default=C.SEED)
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args(argv)


def load_keys() -> dict[str, str]:
    from app.config import get_settings

    s = get_settings()
    return {"tiingo": s.tiingo_api_key.strip(), "finnhub": s.finnhub_api_key.strip(),
            "gemini": s.gemini_api_key.strip(), "newsapi": s.newsapi_key.strip(), "gemini_model": s.gemini_model}


def run_analysis_stages(prices_clean: pd.DataFrame, news_scored: pd.DataFrame, *, cfg: C.PipelineConfig,
                        cards: dict, notes: list[str], force_lstm: bool = False, lstm_max_epochs: int = 50,
                        with_5d_models: bool = True) -> dict:
    """features -> stats -> models -> report. Pure function of its inputs (used by tests too)."""
    from analysis import data_card, features, models, report, stats

    C.set_seeds(cfg.seed)
    feats, news_sess = features.build_feature_table(prices_clean, news_scored, cfg.news_start, cfg.news_end)
    if feats.empty:
        raise ValueError("feature table is empty for the requested window")
    cards["features"] = data_card.build_card(
        feats, name="features", source="Derived: cleaned prices + session-aligned scored news",
        source_url="n/a (computed by analysis/features.py)", retrieval_date=cards.get("prices", {}).get("retrieval_date"),
        duplicates_found=int(feats.duplicated(["ticker", "date"]).sum()), duplicates_removed=0, date_col="date",
        important_columns=data_card.FEATURES_COLUMNS_DOC,
        notes=["Warm-up rows before the analysis window are excluded; see features.py for the timing convention."])
    timing_counts = news_sess["session_timing"].value_counts().to_dict() if len(news_sess) else {}
    notes.append(f"News session timing counts: {timing_counts}")
    data_card.write_cards(cards, cfg.output_dir)
    feats.to_csv(cfg.output_dir / "features.csv", index=False)

    st = stats.run_stats(feats)
    model_results = [models.run_models(feats, target="target_next_1d", seed=cfg.seed,
                                       min_train_sequences=cfg.min_lstm_train_sequences,
                                       force_lstm=force_lstm, lstm_max_epochs=lstm_max_epochs)]
    if with_5d_models:
        model_results.append(models.run_models(feats, target="target_fwd_5d", seed=cfg.seed,
                                               min_train_sequences=cfg.min_lstm_train_sequences,
                                               force_lstm=force_lstm, lstm_max_epochs=lstm_max_epochs))
    for mr in model_results:
        notes.extend(mr.get("notes", []))
        if isinstance(mr.get("predictions"), pd.DataFrame):
            mr["predictions"].to_csv(cfg.output_dir / f"predictions_{mr['target']}.csv", index=False)
    figs = report.make_figures(feats, news_sess, st, model_results, cfg.figures_dir)
    return report.write_report(
        out_dir=cfg.output_dir, tickers=cfg.tickers,
        date_range={"start": cfg.news_start.isoformat(), "end": cfg.news_end.isoformat(),
                    "price_history_start": cfg.price_start.isoformat()},
        cards=cards, stats=st,
        model_results=[{k: v for k, v in m.items() if k != "predictions"} for m in model_results],
        figures=figs, notes=notes,
        run_args={"tickers": cfg.tickers, "days": cfg.days, "warmup_days": cfg.warmup_days,
                  "end_date": cfg.end_date.isoformat(), "use_llm": cfg.use_llm, "offline": cfg.offline,
                  "seed": cfg.seed})


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg = C.PipelineConfig(tickers=args.tickers, days=args.days, warmup_days=args.warmup_days,
                           end_date=args.end_date, use_llm=not args.no_llm, offline=args.offline,
                           use_newsapi=not args.no_newsapi, output_dir=args.output_dir, seed=args.seed)
    C.set_seeds(cfg.seed)

    keys = load_keys()
    if not cfg.offline:
        missing = [n for n, k in (("TIINGO_API_KEY", "tiingo"), ("FINNHUB_API_KEY", "finnhub")) if not keys[k]]
        if missing:
            print(KEY_HELP.format(missing=", ".join(missing)), file=sys.stderr)
            return 2

    from analysis import clean, collect, data_card, sentiment

    cfg.ensure_dirs()
    notes: list[str] = []
    try:
        raw_prices, raw_news = collect.collect_all(cfg, keys)
    except collect.NoCachedDataError as exc:
        print(f"\n--offline: {exc}\nTo populate the cache, add TIINGO_API_KEY and FINNHUB_API_KEY to "
              "backend/.env and run:  python -m analysis.run_pipeline", file=sys.stderr)
        return 2
    except collect.CollectionError as exc:
        print(f"\nData collection failed: {exc}\nCheck your API keys, network and rate limits, then rerun.",
              file=sys.stderr)
        return 3

    prices, p_rep = clean.clean_prices(raw_prices)
    news, n_rep = clean.clean_news(raw_news)
    got = sorted(prices["ticker"].unique())
    if set(got) != set(cfg.tickers):
        notes.append(f"Price data missing for: {sorted(set(cfg.tickers) - set(got))}")

    use_llm = cfg.use_llm and bool(keys["gemini"])
    if cfg.use_llm and not keys["gemini"]:
        notes.append("GEMINI_API_KEY not set: sentiment scored with the deterministic lexicon_v1 fallback.")
    news = sentiment.score_news(news, use_llm=use_llm, api_key=keys["gemini"], model=keys["gemini_model"],
                                cache_path=cfg.raw_dir / "sentiment_cache_gemini.jsonl")
    news_out = news.copy()
    news_out.to_csv(cfg.output_dir / "news_clean.csv", index=False)
    prices.to_csv(cfg.output_dir / "prices_clean.csv", index=False)

    rlog = collect.load_retrieval_log(cfg.raw_dir)
    def _latest(prefix: str) -> str | None:
        ts = [v["retrieved_at"] for k, v in rlog.items() if k.startswith(prefix)]
        return max(ts) if ts else None

    method_counts = news["sentiment_method"].value_counts().to_dict() if len(news) else {}
    cards = {
        "prices": data_card.build_card(
            prices, name="prices", source="Tiingo daily prices (end-of-day, adjusted)",
            source_url=C.TIINGO_URL.format(ticker="{TICKER}"), retrieval_date=_latest("prices_"),
            duplicates_found=p_rep["duplicates_found"], duplicates_removed=p_rep["duplicates_removed"],
            date_col="date", important_columns=data_card.PRICE_COLUMNS_DOC,
            notes=[f"Cleaning steps: {p_rep['steps']}", f"Validation violations dropped: {p_rep['validation_violations']}"]),
        "news": data_card.build_card(
            news, name="news", source="Finnhub company-news" + (" + NewsAPI (optional)" if keys["newsapi"] else ""),
            source_url=C.FINNHUB_NEWS_URL, retrieval_date=_latest("news_"),
            duplicates_found=n_rep["duplicates_found"], duplicates_removed=n_rep["duplicates_removed"],
            date_col="published_utc", important_columns=data_card.NEWS_COLUMNS_DOC,
            notes=[f"Cleaning steps: {n_rep['steps']}", f"Sentiment methods used: {method_counts}"]),
    }
    try:
        results = run_analysis_stages(prices, news, cfg=cfg, cards=cards, notes=notes)
    except ValueError as exc:
        print(f"\nAnalysis could not run: {exc}", file=sys.stderr)
        return 3
    log.info("Done. Report: %s ; results: %s", cfg.output_dir / "report.md", cfg.output_dir / "results.json")
    log.info("Models (test RMSE): %s", {k: v.get("rmse") for k, v in results["models"].items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
