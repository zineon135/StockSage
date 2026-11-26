# Stock Sage

**Smarter Insights. Better Understanding. Confident Decisions.**

Stock Sage is an AI-powered stock analysis and investing-education platform. It combines real market data, programmatically calculated technical indicators, financial news, a Gemini-powered research analyst and a $100,000 paper-trading simulator.

> Stock Sage is an educational financial analysis platform. It does not provide personalized financial advice, investment recommendations, or guarantees of future performance. All simulated transactions use virtual funds and do not represent actual financial trades. Financial information may be delayed, incomplete, or inaccurate. Always conduct independent research before making financial decisions.

---

## Features

| Area | What it does |
|---|---|
| **Dashboard** | Index proxies (SPY, QQQ, DIA, IWM), market status, trending stocks, gainers and losers, market breadth, unusual volume, AI market insights, portfolio summary |
| **Explore / Stock pages** | Search by name or ticker. Quote, profile, key stats, 52-week range, interactive chart (1D–5Y) with 50/200-day averages |
| **Technicals** | 50/200-day SMA, RSI(14), 30-day annualized volatility, volume vs. average, returns and max drawdown. All computed in Python and explained in plain language |
| **AI Analyst** | Chat and a 9-section report (overview, performance, bullish, bearish, news, technical, historical, assessment, risks). Every claim is cited and labelled as fact or interpretation |
| **News & sentiment** | Market, economy, technology and company news. Gemini classifies sentiment and explains why |
| **Watchlist** | Persistent list with live quotes and 30-day sparklines |
| **Paper trading** | $100k of virtual cash; buy and sell whole shares at the latest quote. Every transaction records the price and its market timestamp |
| **Portfolio** | Value, cash, cost basis, unrealized and realized P&L, allocation chart, performance snapshots, history |
| **Learning Center** | Plain-language glossary, also shown as hover tooltips across the app (Beginner mode) |
| **Research pipeline** | Reproducible Python pipeline: data collection, cleaning, data cards, features, sentiment–return statistics, baselines → LSTM ([backend/analysis/README.md](backend/analysis/README.md)) |

---

## Architecture

```
frontend/  React 19 + TypeScript + Vite + Tailwind v4 + Recharts + Lucide
   └─ talks ONLY to /api/* (Vite proxies to the backend; no API keys in the browser)

backend/   FastAPI + SQLAlchemy (SQLite → PostgreSQL-ready)
   app/services/market_data.py   Financial Data Service   (Finnhub, Tiingo, Alpha Vantage)
   app/services/news.py          News Service             (NewsAPI + Finnhub news)
   app/services/analytics.py     Analytics Service        (SMA, RSI, volatility, drawdown)
   app/services/context.py       Builds the source-attributed data package for the AI
   app/services/ai.py            AI Service               (Gemini; interprets, never computes)
   app/services/trading.py       Paper-trading engine     (Decimal accounting)
   app/core/cache.py             TTL cache + last-known-good store (stale-data fallback)
   analysis/                     Research and ML pipeline
```

**How the AI stays reliable**

1. Stock Sage retrieves the quote, profile, metrics, history and news from the providers, then computes the indicators in Python.
2. Each item becomes a source with an ID (`Q1`, `P1`, `M1`, `T1`, `C1`, `N1…`) and its timestamps.
3. Gemini receives **only** that package, with strict rules and a JSON schema (`responseJsonSchema`).
4. The output is validated:
   - Citations to sources that don't exist are removed.
   - "Facts" without a source become interpretations.
   - Any number in a fact must match a retrieved number, allowing only for rounding to the precision written; otherwise it is downgraded and flagged.
   - Guarantee or recommendation language is flagged.
5. The UI shows facts and interpretations differently, with clickable source citations and timestamps.

**Stale data.** When a provider fails, the backend serves the last successful payload with `stale: true` and its **original** retrieval time. The UI then shows a visible "Stale data" warning. Paper trades refuse to execute on stale prices.

---

## Setup

Requirements: **Node 20+**, **Python 3.12**.

### 1. Backend

```bash
cd backend
python -m venv .venv
# Windows:  .venv\Scripts\activate      macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then add your API keys (see below)
uvicorn app.main:app --reload --port 8000
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev                   # http://localhost:5173
```

The app runs without keys. Each panel then explains which key it needs, and paper-trading state, the watchlist and settings still persist.

### API keys

All keys go in `backend/.env`. They are never exposed to the browser, and `.env` is git-ignored.

| Variable | Provider | Used for | Free-tier notes (verified Nov 2026) |
|---|---|---|---|
| `FINNHUB_API_KEY` | [Finnhub](https://finnhub.io/register) | Quotes, profile, metrics, search, market status, company/general news, peers | ~60 calls/min. **Historical candles are premium-only.** Index levels (^GSPC) not available, so ETF proxies are used |
| `TIINGO_API_KEY` | [Tiingo](https://www.tiingo.com/account/api/token) | Daily price history (charts, indicators, sparklines, ML) | 50 requests/hour, 1,000/day, internal use. History is fetched once per symbol per day and cached |
| `NEWSAPI_KEY` | [NewsAPI](https://newsapi.org/register) | News headlines | Developer plan: 100 req/day, **24h delay**, ~1 month of search, **development use only** (production needs a paid plan) |
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/apikey) | AI Analyst, insights, sentiment | `GEMINI_MODEL` defaults to `gemini-3.8-flash` (`gemini-2.5-flash` is deprecated). If it is overloaded (503/429/timeout), `GEMINI_FALLBACK_MODELS` (default `gemini-3.1-flash-lite`) is tried within `GEMINI_TOTAL_TIMEOUT` (75 s). Each AI response reports the model that actually answered |
| `ALPHAVANTAGE_API_KEY` | [Alpha Vantage](https://www.alphavantage.co/support/#api-key) *(optional)* | History fallback | 25 req/day, last ~100 trading days only |
| `ALPACA_API_KEY_ID`, `ALPACA_API_SECRET_KEY` | [Alpaca](https://app.alpaca.markets/signup) *(optional)* | Paper Trading → "Alpaca paper account" tab: orders routed to Alpaca's **paper** environment | Free. Use keys from the **Paper** account. Stock Sage's broker URL is hard-coded to `paper-api.alpaca.markets`; it cannot place real-money trades |

**Why Tiingo?** The brief named Finnhub and NewsAPI. However, Finnhub's free plan excludes historical candles, and Stooq's free CSV endpoint now sits behind a browser bot check. Tiingo's free tier is the most practical official source for daily history.

---

## Tests

```bash
cd backend && .venv/Scripts/python -m pytest -q     # 67 tests
cd frontend && npm test && npm run build
```

The backend tests cover:

- **Indicator math:** RSI against a published worksheet, SMA, volatility and drawdown.
- **Paper-trading accounting:** weighted average cost, realized P&L, insufficient funds and shares, quantity validation.
- **Stale-cache fallback.**
- **AI output validation:** number, citation and guarantee checks.
- **API routes.**
- **Provider clients:** Finnhub, Tiingo, NewsAPI and Gemini against mocked HTTP responses shaped like their documented formats.
- **The research pipeline,** using synthetic test fixtures only.

---

## Known limitations

These are stated plainly because accuracy matters more than appearances.

- **Live integration status (tested 25 Nov 2026 with real free-tier keys):** Finnhub (quotes, profile, metrics, search, market status, news), Tiingo (5 years of adjusted daily history, and 1D intraday IEX bars on the free plan), NewsAPI and Gemini all returned and parsed correctly. During testing, `gemini-3.8-flash` was overloaded (HTTP 503 and timeouts), so AI requests were answered by the fallback model; expect slower AI responses (up to ~50 s) when that happens. Alpha Vantage (fallback only) was not exercised because Tiingo succeeded.
- **Finnhub's "general" news feed** (used in Markets/Economy) includes some world and political headlines; it is shown as Finnhub categorizes it, not filtered by topic.
- **Index values are ETF proxies** (SPY, QQQ, DIA, IWM). Their percentage moves track the index closely, but their prices are not index levels.
- **Trending stocks, gainers and losers** come from a fixed, documented universe of 30 large-cap US stocks, because free plans have no market-wide movers feed.
- **The 1D intraday chart** uses Tiingo's IEX endpoint (worked on a free account in testing). If it becomes unavailable the chart shows a clear message.
- **Volume** comes from end-of-day data, so it reflects the last completed session (labelled as such). Finnhub's free quote has no volume.
- **Company description:** Finnhub's free profile has no written business description. The app shows the industry, exchange, IPO date and website, and marks the rest N/A.
- **The quote timestamp** is Finnhub's. Whether free quotes are real-time or delayed isn't documented, so the UI always shows the timestamp and never claims "real-time".
- **NewsAPI's Developer plan** is limited to development use, and its articles are delayed 24 hours.
- **Alpaca paper integration** was tested live on 25 Nov 2026 against a real paper account (account, clock, positions, orders, placing and cancelling a limit order) while the market was closed, so no live fill has been observed yet. Alpaca paper accounts allow short selling by default; Stock Sage blocks sells larger than the shares held (minus open sell orders). Orders are whole-share market or limit day orders; every order needs an explicit confirmation.
- **Real-money trading is intentionally not supported.** It would require user authentication, secure per-user credential storage, order limits and regulatory review.
- **Simulator fills** are idealized: latest quote, no spread or slippage, whole shares, no trading-hours enforcement.
- **Single demo user.** The schema has a `users` table, but authentication is not implemented.
- **scikit-learn's compiled DLLs are blocked** by Windows Application Control on the development machine, so the pipeline implements Ridge regression with numpy.

## Database

SQLite at `backend/data/stocksage.db`. The tables are `users`, `user_settings`, `watchlist_items`, `portfolios`, `holdings`, `transactions`, `portfolio_snapshots` and `cache_entries`. They use portable types (`NUMERIC(18,4)` for money).

To switch to PostgreSQL, set `DATABASE_URL=postgresql+psycopg://…` and install `psycopg[binary]`; the tables are created on startup. For production schema changes, add Alembic.

## Data attribution

- Market data: [Finnhub](https://finnhub.io/) and [Tiingo](https://www.tiingo.com/).
- News: [NewsAPI](https://newsapi.org/) and Finnhub. Only headlines and short summaries are shown, with links to the original publishers.
- AI: [Google Gemini](https://ai.google.dev/).
