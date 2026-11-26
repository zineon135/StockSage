"""Application configuration loaded from environment variables (never hardcode secrets)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    # --- Credentials (backend only; never sent to the browser) ---
    finnhub_api_key: str = ""
    newsapi_key: str = ""
    gemini_api_key: str = ""
    tiingo_api_key: str = ""  # daily price history (Finnhub candles are premium-only)
    alphavantage_api_key: str = ""  # optional fallback for historical prices
    # Alpaca brokerage PAPER account (simulated orders through a real broker; no real money).
    alpaca_api_key_id: str = ""
    alpaca_api_secret_key: str = ""

    # --- AI ---
    # gemini-2.5-flash is deprecated (Nov 2026); override with GEMINI_MODEL if needed.
    gemini_model: str = "gemini-3.8-flash"
    # Tried in order when the primary model is overloaded (HTTP 503/429/5xx or timeout).
    # Comma-separated; set to an empty string to disable fallback.
    gemini_fallback_models: str = "gemini-3.1-flash-lite"
    # Upper bound on how long one AI request may take across all attempts.
    gemini_total_timeout: float = 75.0

    @property
    def gemini_model_chain(self) -> list[str]:
        chain = [self.gemini_model] + [m.strip() for m in self.gemini_fallback_models.split(",") if m.strip()]
        return list(dict.fromkeys(chain))  # de-duplicate, keep order

    # --- Infrastructure ---
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'data' / 'stocksage.db').as_posix()}"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    log_level: str = "INFO"

    # --- Rate limits (requests per minute we allow ourselves to send) ---
    finnhub_rpm: int = 55  # free tier is 60/min; keep headroom

    # --- Paper trading ---
    starting_cash: float = 100_000.00

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
