"""Stock Sage API entry point.  Run: uvicorn app.main:app --reload --port 8000"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .core.errors import register_error_handlers
from .core.http import close_client
from .database import init_db
from .routers import ai_routes, broker, market, news, stocks, user
from .services import market_data as md

DISCLAIMER = (
    "Stock Sage is an educational financial analysis platform. It does not provide personalized financial advice, "
    "investment recommendations, or guarantees of future performance. All simulated transactions use virtual funds and "
    "do not represent actual financial trades. Financial information may be delayed, incomplete, or inaccurate. Always "
    "conduct independent research before making financial decisions."
)

logging.basicConfig(
    level=get_settings().log_level.upper(),
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)
# httpx logs full URLs at INFO; keep it quiet so nothing sensitive is logged.
logging.getLogger("httpx").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield
    await close_client()


app = FastAPI(title="Stock Sage API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)
register_error_handlers(app)

for r in (market.router, stocks.router, news.router, ai_routes.router, user.router, broker.router):
    app.include_router(r)


@app.get("/api/system/status")
def system_status():
    s = get_settings()
    return {
        "server_time": datetime.now(timezone.utc).isoformat(),
        "providers": md.configured_providers(),
        "ai_model": s.gemini_model,
        "disclaimer": DISCLAIMER,
        "data_notes": [
            "Quotes: Finnhub. Timestamps shown are the provider's price timestamps.",
            "Index values are shown via ETFs that track each index (SPY, QQQ, DIA, IWM).",
            "Historical daily prices: Tiingo end-of-day data (Finnhub's free plan excludes historical candles).",
            "News: NewsAPI (Developer plan: 24-hour delay, development use only) and Finnhub.",
        ],
    }
