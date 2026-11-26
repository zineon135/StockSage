# Stock Sage research pipeline (`backend/analysis/`)

Reproducible pipeline for the research question:

> Using historical stock market data and financial news, what observable factors are associated with
> positive or negative stock performance over a selected period, and how can those factors help identify
> potential opportunities and risks?

Educational analysis only — not investment advice.

## Run

From the `backend` directory:

```powershell
.venv\Scripts\python.exe -m analysis.run_pipeline                     # defaults: 10 tickers, last 365 days
.venv\Scripts\python.exe -m analysis.run_pipeline --tickers AAPL MSFT --days 365
.venv\Scripts\python.exe -m analysis.run_pipeline --no-llm            # lexicon sentiment only
.venv\Scripts\python.exe -m analysis.run_pipeline --offline           # cached raw CSVs only, no network
```

Other flags: `--warmup-days` (extra price history for SMA200, default 730), `--end-date YYYY-MM-DD`,
`--no-newsapi`, `--output-dir`, `--seed`, `-v`.

Exit codes: `0` success · `2` required keys missing (or `--offline` with no cache) · `3` collection/analysis failed.

## API keys (`backend/.env`)

| Variable | Required | Used for |
|---|---|---|
| `TIINGO_API_KEY` | yes | Daily adjusted OHLCV (free: 50 req/hour, 1000/day) |
| `FINNHUB_API_KEY` | yes | Company news, ~1 year history, fetched in monthly chunks (60 calls/min) |
| `GEMINI_API_KEY` (+ `GEMINI_MODEL`) | no | LLM headline sentiment; otherwise the deterministic `lexicon_v1` scorer |
| `NEWSAPI_KEY` | no | Optional ~1-month news supplement |

A first full run of 10 tickers needs 10 Tiingo calls (the limiter spaces them ~75 s apart to respect
50/hour, so allow ~12 minutes) and ~130 Finnhub calls. Reruns reuse `output/raw/` caches.

## Pipeline stages

| Module | Purpose |
|---|---|
| `config.py` | Tickers, windows, thresholds, output paths, seeding |
| `collect.py` | HTTP retrieval with retries/backoff, rate limiting, CSV caching, retrieval log |
| `clean.py` | Missing values, duplicates, validation, timestamp normalisation (UTC → America/New_York) |
| `sentiment.py` | Gemini structured-output scoring (cached jsonl) or `lexicon_v1` fallback; `sentiment_method` column |
| `data_card.py` | `output/data_card.md` + `.json` for prices, news and features |
| `features.py` | Returns, volatility, SMA ratios, RSI14, volume z-score, news counts/sentiment, targets |
| `stats.py` | Pearson/Spearman, bucket means with bootstrap CIs, Welch / Kruskal tests, Benjamini–Hochberg |
| `models.py` | Chronological split; naive zero, historical mean, ridge; then LSTM (skipped if < 500 train sequences) |
| `report.py` | `output/report.md`, `output/results.json`, `output/figures/*.png` |
| `run_pipeline.py` | CLI entry point running everything in order |

## Outputs (`analysis/output/`)

`raw/` (cached API responses + `retrieval_log.json` + Gemini cache) · `prices_clean.csv` · `news_clean.csv` ·
`features.csv` · `predictions_*.csv` · `data_card.md/json` · `report.md` · `results.json` · `figures/`.

`results.json` schema: `{generated_at, tickers, date_range, data_cards:{prices,news,features},
stats:{...}, models:{name:{mae, rmse, directional_accuracy, n_test}}, notes:[...], run_args}`.
Next-day models are keyed `naive_zero`, `historical_mean`, `ridge`, `lstm`; 5-day models add `_5d`.

## Methodology highlights

* **No synthetic data in the pipeline.** Failed downloads are reported, never filled. Synthetic data exists
  only inside `tests/test_analysis_pipeline.py`.
* **Prices:** rows missing close/volume dropped, never forward-filled; (ticker, date) duplicates removed;
  OHLC sanity checks. Returns use `adj_close`.
* **Leakage-safe news alignment (America/New_York):** before 09:30 on a trading day → that session
  (`pre_market`); 09:30–16:00 → that session, flagged `intraday`; after 16:00 or weekend/holiday → next
  trading session (calendar = dates in the price data). Features on row t use only data available by the
  close of t.
* **Targets:** same-day `adj_close[t]/adj_close[t-1]-1`; next-day `adj_close[t+1]/adj_close[t]-1`;
  5-day `adj_close[t+5]/adj_close[t]-1`.
* **Modelling:** dates split 70/15/15 in order (pooled across tickers, no shuffling), an embargo of h
  sessions between splits so labels never overlap the next split, scaler fit on train only. Ridge is a
  numpy closed-form implementation (scikit-learn's compiled DLLs are blocked by Windows Application
  Control on the dev machine). Expect no model to beat the naive baseline reliably.
* **Statistics:** correlation ≠ causation; all p-values Benjamini–Hochberg adjusted; 5-day overlapping
  returns make p-values optimistic.

## Tests

```powershell
cd backend
.venv\Scripts\python.exe -m pytest tests/test_analysis_pipeline.py -q
```
