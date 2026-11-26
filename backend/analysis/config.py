"""Static configuration for the Stock Sage research pipeline.

Everything that controls *what* is analysed lives here so a run can be reproduced
from the CLI arguments recorded in ``output/results.json``.
"""
from __future__ import annotations

import os
import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import numpy as np

ANALYSIS_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = ANALYSIS_DIR / "output"

DEFAULT_TICKERS: list[str] = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "JPM", "XOM", "JNJ"]

# Company names are only used to build NewsAPI keyword queries (optional supplement).
COMPANY_NAMES: dict[str, str] = {
    "AAPL": "Apple", "MSFT": "Microsoft", "NVDA": "Nvidia", "AMZN": "Amazon", "GOOGL": "Alphabet",
    "META": "Meta Platforms", "TSLA": "Tesla", "JPM": "JPMorgan", "XOM": "Exxon Mobil", "JNJ": "Johnson & Johnson",
}

DEFAULT_DAYS = 365          # analysis window; matches Finnhub free-plan news history (~1 year)
DEFAULT_WARMUP_DAYS = 730   # extra calendar days of prices so SMA200 etc. are defined on day 1 of the window
SEED = 42

# Market session boundaries in America/New_York (regular hours only; early closes are not modelled).
MARKET_TZ = "America/New_York"
MARKET_OPEN = (9, 30)
MARKET_CLOSE = (16, 0)

# Sentiment bucket thresholds on the per-day mean sentiment score (-1..1).
SENTIMENT_NEG_THRESHOLD = -0.1
SENTIMENT_POS_THRESHOLD = 0.1

TIINGO_URL = "https://api.tiingo.com/tiingo/daily/{ticker}/prices"
FINNHUB_NEWS_URL = "https://finnhub.io/api/v1/company-news"
NEWSAPI_URL = "https://newsapi.org/v2/everything"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


@dataclass
class PipelineConfig:
    tickers: list[str] = field(default_factory=lambda: list(DEFAULT_TICKERS))
    days: int = DEFAULT_DAYS
    warmup_days: int = DEFAULT_WARMUP_DAYS
    end_date: date = field(default_factory=date.today)
    use_llm: bool = True
    offline: bool = False
    use_newsapi: bool = True
    output_dir: Path = OUTPUT_DIR
    seed: int = SEED
    min_lstm_train_sequences: int = 500

    def __post_init__(self) -> None:
        self.tickers = sorted({t.strip().upper() for t in self.tickers if t.strip()})
        self.output_dir = Path(self.output_dir)

    @property
    def news_start(self) -> date:
        return self.end_date - timedelta(days=self.days)

    @property
    def news_end(self) -> date:
        return self.end_date

    @property
    def price_start(self) -> date:
        return self.news_start - timedelta(days=self.warmup_days)

    @property
    def raw_dir(self) -> Path:
        return self.output_dir / "raw"

    @property
    def figures_dir(self) -> Path:
        return self.output_dir / "figures"

    def ensure_dirs(self) -> None:
        for d in (self.output_dir, self.raw_dir, self.figures_dir):
            d.mkdir(parents=True, exist_ok=True)


def set_seeds(seed: int = SEED) -> None:
    """Seed every RNG the pipeline touches (python, numpy, torch if available)."""
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    np.random.seed(seed)
    try:
        import torch

        torch.manual_seed(seed)
        torch.set_num_threads(1)  # deterministic CPU reductions
    except ImportError:  # pragma: no cover
        pass
