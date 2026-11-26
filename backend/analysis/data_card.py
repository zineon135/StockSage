"""Auto-generated data cards (markdown + JSON) for every dataset the pipeline produces."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

REQUIRED_FIELDS = [
    "dataset_name", "data_source", "source_url", "retrieval_date", "rows", "columns", "column_names", "dtypes",
    "missing_values", "duplicates_found", "duplicates_removed", "date_range", "important_columns",
]

PRICE_COLUMNS_DOC = {
    "ticker": "Upper-case stock symbol.",
    "date": "Trading date (exchange calendar day of the bar).",
    "close": "Unadjusted closing price (used only for validation).",
    "adj_close": "Split/dividend-adjusted close; ALL returns and indicators are computed from this.",
    "high": "Unadjusted session high (validation: high >= low/open/close).",
    "low": "Unadjusted session low.",
    "volume": "Unadjusted share volume.",
    "adj_volume": "Split-adjusted volume; used for volume change / z-score features.",
}

NEWS_COLUMNS_DOC = {
    "ticker": "Stock the article was retrieved for.",
    "article_id": "Provider article id (NewsAPI: hash of URL); dedupe key.",
    "published_utc": "Publication time in UTC (from unix epoch).",
    "published_et": "Publication time in America/New_York; used for session alignment.",
    "headline": "Article headline; primary sentiment input.",
    "summary": "Provider summary; secondary sentiment input.",
    "sentiment_score": "Sentiment in [-1, 1].",
    "sentiment_method": "Which scorer produced the score (gemini:<model> or lexicon_v1).",
    "session_date": "Trading session the article is assigned to (leakage-safe, see features.py).",
    "session_timing": "pre_market | intraday | after_close | non_trading_day.",
}

FEATURES_COLUMNS_DOC = {
    "ret": "Same-day simple return adj_close[t]/adj_close[t-1]-1 (also the 'same-day' target).",
    "target_next_1d": "Next-session return adj_close[t+1]/adj_close[t]-1 (prediction target).",
    "target_fwd_5d": "Cumulative return over sessions t+1..t+5: adj_close[t+5]/adj_close[t]-1.",
    "vol20": "Annualised 20-session volatility of log returns (through t).",
    "vol30": "Annualised 30-session volatility of log returns (through t).",
    "rsi14": "Wilder RSI(14) of adj_close through t.",
    "px_sma200": "adj_close / SMA200 - 1.",
    "volume_z": "Volume z-score vs the PRIOR 20 sessions.",
    "news_count": "Articles assigned to session t (0 if none).",
    "sentiment_mean": "Mean sentiment of articles assigned to session t (NaN if none).",
}


def _jsonable(v: Any) -> Any:
    if isinstance(v, (pd.Timestamp, datetime)):
        return v.isoformat()
    if hasattr(v, "item"):
        return v.item()
    return v


def build_card(df: pd.DataFrame, *, name: str, source: str, source_url: str, retrieval_date: str | None,
               duplicates_found: int, duplicates_removed: int, date_col: str | None,
               important_columns: dict[str, str], notes: list[str] | None = None) -> dict:
    date_range = None
    if date_col and date_col in df.columns and len(df):
        s = pd.to_datetime(df[date_col], utc=date_col.endswith("_utc"),errors="coerce")
        date_range = {"start": _jsonable(s.min()), "end": _jsonable(s.max())}
    return {
        "dataset_name": name,
        "data_source": source,
        "source_url": source_url,
        "retrieval_date": retrieval_date or "unknown",
        "rows": int(len(df)),
        "columns": int(df.shape[1]),
        "column_names": list(map(str, df.columns)),
        "dtypes": {str(c): str(t) for c, t in df.dtypes.items()},
        "missing_values": {str(c): int(v) for c, v in df.isna().sum().items()},
        "duplicates_found": int(duplicates_found),
        "duplicates_removed": int(duplicates_removed),
        "date_range": date_range,
        "important_columns": {k: v for k, v in important_columns.items() if k in df.columns},
        "notes": notes or [],
        "card_generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def card_to_markdown(card: dict) -> str:
    lines = [f"## {card['dataset_name']}", "",
             f"- **Data source:** {card['data_source']}",
             f"- **Source URL:** {card['source_url']}",
             f"- **Retrieval date:** {card['retrieval_date']}",
             f"- **Rows x columns:** {card['rows']} x {card['columns']}",
             f"- **Duplicates found / removed:** {card['duplicates_found']} / {card['duplicates_removed']}"]
    dr = card.get("date_range")
    lines.append(f"- **Date range:** {dr['start']} to {dr['end']}" if dr else "- **Date range:** n/a")
    lines += ["", "| Column | dtype | Missing |", "|---|---|---|"]
    for c in card["column_names"]:
        lines.append(f"| `{c}` | {card['dtypes'][c]} | {card['missing_values'][c]} |")
    lines += ["", "**Important columns**", ""]
    lines += [f"- `{k}`: {v}" for k, v in card["important_columns"].items()]
    if card.get("notes"):
        lines += ["", "**Notes**", ""] + [f"- {n}" for n in card["notes"]]
    return "\n".join(lines) + "\n"


def write_cards(cards: dict[str, dict], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "data_card.json").write_text(json.dumps(cards, indent=2, default=str), encoding="utf-8")
    md = ["# Stock Sage research pipeline - data cards", "",
          "Auto-generated by `analysis/data_card.py`. One card per dataset.", ""]
    md += [card_to_markdown(c) for c in cards.values()]
    (out_dir / "data_card.md").write_text("\n".join(md), encoding="utf-8")
