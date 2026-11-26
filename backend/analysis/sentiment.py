"""Headline sentiment scoring.

Two methods, and every scored row records which one produced it (``sentiment_method``):

1. ``gemini:<model>`` — Gemini structured-output classification of headline + summary into
   {sentiment: positive|negative|neutral, score: -1..1}. Batched (~20/call) and cached in
   ``raw/sentiment_cache_gemini.jsonl`` keyed by ``ticker|article_id`` so reruns cost no quota.
2. ``lexicon_v1`` — transparent, deterministic fallback used when no GEMINI_API_KEY is set,
   ``--no-llm`` is passed, or a Gemini batch fails.

Lexicon method (lexicon_v1)
---------------------------
* Text = headline + " " + summary, lower-cased, tokenised on [a-z']+.
* Each token found in POSITIVE_WORDS counts +1, in NEGATIVE_WORDS counts -1.
* Negation: if any of NEGATORS appears within the 3 preceding tokens, the polarity flips.
* score = (pos - neg) / (pos + neg), or 0.0 when no lexicon word is found.
  The headline is counted twice (it is the most informative text).
* label = positive if score >= 0.2, negative if score <= -0.2, else neutral.
The word lists are small, finance-oriented and hand-picked (inspired by the general idea of the
Loughran–McDonald finance dictionary, but NOT a copy of it). It is a crude baseline: it ignores
sarcasm, context ("loss narrows"), and entity targeting. Results should be read as such.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import httpx
import pandas as pd

from analysis import config as C

log = logging.getLogger(__name__)

LEXICON_METHOD = "lexicon_v1"

POSITIVE_WORDS = frozenset("""
beat beats beating exceed exceeds exceeded outperform outperforms outperformed surge surges surged soar soars
soared rally rallies rallied jump jumps jumped gain gains gained rise rises rising rose record growth grow grows
grew strong stronger strongest profit profitable profits upgrade upgraded upgrades bullish boost boosts boosted
expand expands expansion win wins won approval approved breakthrough optimistic optimism rebound rebounds
rebounded raise raises raised dividend buyback innovative innovation momentum robust upbeat higher top tops
""".split())

NEGATIVE_WORDS = frozenset("""
miss misses missed fall falls fell drop drops dropped plunge plunges plunged slump slumps slumped decline
declines declined loss losses lose loses losing weak weaker weakest downgrade downgraded downgrades bearish
lawsuit lawsuits sue sued probe investigation fraud recall recalls layoff layoffs cut cuts cutting warn warns
warning warned risk risks concern concerns crash crashes crashed tumble tumbles tumbled sink sinks sank slow
slows slowdown fined penalty halt halted delay delays delayed lower bankruptcy default selloff sell-off
antitrust scrutiny disappointing disappoint disappoints shortfall volatile uncertainty
""".split())

NEGATORS = frozenset({"not", "no", "never", "without", "isn't", "doesn't", "didn't", "won't", "fails", "failed"})

_TOKEN = re.compile(r"[a-z][a-z'\-]*")


def lexicon_score(headline: str, summary: str = "") -> tuple[str, float]:
    text = f"{headline or ''} {headline or ''} {summary or ''}".lower()
    tokens = _TOKEN.findall(text)
    pos = neg = 0
    for i, tok in enumerate(tokens):
        pol = 1 if tok in POSITIVE_WORDS else -1 if tok in NEGATIVE_WORDS else 0
        if pol == 0:
            continue
        if any(t in NEGATORS for t in tokens[max(0, i - 3):i]):
            pol = -pol
        if pol > 0:
            pos += 1
        else:
            neg += 1
    score = 0.0 if pos + neg == 0 else (pos - neg) / (pos + neg)
    label = "positive" if score >= 0.2 else "negative" if score <= -0.2 else "neutral"
    return label, float(score)


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "sentiment": {"type": "string", "enum": ["positive", "negative", "neutral"]},
                    "score": {"type": "number", "minimum": -1, "maximum": 1},
                },
                "required": ["id", "sentiment", "score"],
            },
        }
    },
    "required": ["results"],
}

PROMPT = (
    "You are a financial news sentiment classifier. For each article below, judge the sentiment of the "
    "news FOR THE NAMED COMPANY'S STOCK (not the market in general). Return sentiment "
    "(positive|negative|neutral) and a score from -1 (very negative) to 1 (very positive); use 0 for neutral "
    "or irrelevant items. Return one result per input id, echoing the id exactly.\n\nArticles (JSON):\n"
)


def _cache_key(ticker: str, article_id: str) -> str:
    return f"{ticker}|{article_id}"


def load_cache(path: Path) -> dict[str, dict]:
    cache: dict[str, dict] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
                cache[rec["key"]] = rec
            except (json.JSONDecodeError, KeyError):
                continue
    return cache


def _gemini_batch(client: httpx.Client, api_key: str, model: str, items: list[dict]) -> dict[str, dict]:
    body = {
        "contents": [{"role": "user", "parts": [{"text": PROMPT + json.dumps(items, ensure_ascii=False)}]}],
        "generationConfig": {"responseMimeType": "application/json", "responseJsonSchema": RESPONSE_SCHEMA,
                             "temperature": 0},
    }
    r = client.post(C.GEMINI_URL.format(model=model), json=body,
                    headers={"x-goog-api-key": api_key, "Content-Type": "application/json"}, timeout=90.0)
    r.raise_for_status()
    parts = r.json()["candidates"][0]["content"]["parts"]
    text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    parsed = json.loads(text)
    out = {}
    for res in parsed.get("results", []):
        label = res.get("sentiment")
        if label not in ("positive", "negative", "neutral"):
            continue
        out[str(res.get("id"))] = {"sentiment": label, "score": max(-1.0, min(1.0, float(res.get("score", 0))))}
    return out


def score_news(news: pd.DataFrame, *, use_llm: bool, api_key: str = "", model: str = "",
               cache_path: Path | None = None, batch_size: int = 20) -> pd.DataFrame:
    """Add ``sentiment_label``, ``sentiment_score`` and ``sentiment_method`` columns."""
    news = news.copy()
    labels: list[str] = []
    scores: list[float] = []
    methods: list[str] = []
    if news.empty:
        for c in ("sentiment_label", "sentiment_score", "sentiment_method"):
            news[c] = pd.Series(dtype="object" if c != "sentiment_score" else float)
        return news

    llm_results: dict[str, dict] = {}
    if use_llm and api_key and model:
        cache_path = cache_path or (C.OUTPUT_DIR / "raw" / "sentiment_cache_gemini.jsonl")
        cache = load_cache(cache_path)
        method = f"gemini:{model}"
        todo = [r for r in news.itertuples() if _cache_key(r.ticker, r.article_id) not in cache]
        log.info("sentiment: %d cached, %d to classify with %s", len(news) - len(todo), len(todo), model)
        with httpx.Client() as client, cache_path.open("a", encoding="utf-8") as fh:
            for i in range(0, len(todo), batch_size):
                batch = todo[i:i + batch_size]
                items = [{"id": str(j), "company_ticker": r.ticker, "headline": r.headline,
                          "summary": (r.summary or "")[:600]} for j, r in enumerate(batch)]
                try:
                    res = _gemini_batch(client, api_key, model, items)
                except Exception as exc:  # noqa: BLE001 - any failure -> lexicon fallback for this batch
                    log.warning("sentiment: Gemini batch failed (%s); lexicon fallback for %d items", exc, len(batch))
                    continue
                for j, r in enumerate(batch):
                    if str(j) in res:
                        rec = {"key": _cache_key(r.ticker, r.article_id), "method": method, **res[str(j)]}
                        cache[rec["key"]] = rec
                        fh.write(json.dumps(rec) + "\n")
        llm_results = cache

    for r in news.itertuples():
        rec = llm_results.get(_cache_key(r.ticker, r.article_id))
        if rec is not None:
            labels.append(rec["sentiment"]); scores.append(float(rec["score"])); methods.append(rec["method"])
        else:
            lab, sc = lexicon_score(r.headline, r.summary)
            labels.append(lab); scores.append(sc); methods.append(LEXICON_METHOD)
    news["sentiment_label"] = labels
    news["sentiment_score"] = scores
    news["sentiment_method"] = methods
    return news
