import time
from datetime import datetime

import feedparser

CACHE_TTL = 1800  # 30 minutes

_cache: dict = {}

RSS_FEEDS = [
    ("Kitco News",    "https://www.kitco.com/rss/kitconews_gold.rss"),
    ("Yahoo Finance", "https://feeds.finance.yahoo.com/rss/2.0/headline?s=GC%3DF&region=US&lang=en-US"),
]

GOLD_TERMS = [
    "gold", "xau", "bullion", "precious metal", "emas",
    "fed", "federal reserve", "inflation", "dollar", "safe haven",
    "interest rate", "treasury", "commodity",
]

BULLISH_TERMS = [
    "war", "conflict", "tensions", "geopolitical", "crisis",
    "inflation", "safe haven", "rate cut", "dovish", "recession",
    "uncertainty", "weak dollar", "dollar falls", "dollar drops",
    "sanctions", "tariff", "surge", "rally", "soars", "jumps",
    "gains", "record high", "demand", "risk-off", "fear",
    "debt ceiling", "banking crisis", "volatility", "haven",
    "stagflation", "hyperinflation", "devaluation",
]

BEARISH_TERMS = [
    "rate hike", "rate increase", "hawkish", "strong dollar",
    "dollar rallies", "dollar rises", "dollar strengthens",
    "risk-on", "recovery", "selloff", "sell-off", "drops",
    "falls", "decline", "weakens", "profit taking", "tightening",
    "yields rise", "economic growth", "outflows", "pressure",
]


def _is_gold_relevant(text: str) -> bool:
    t = text.lower()
    return any(term in t for term in GOLD_TERMS)


def _score(text: str) -> int:
    t = text.lower()
    score = 0
    for term in BULLISH_TERMS:
        if term in t:
            score += 1
    for term in BEARISH_TERMS:
        if term in t:
            score -= 1
    return score


def fetch_sentiment() -> dict:
    now = time.monotonic()
    if "data" in _cache and now - _cache["ts"] < CACHE_TTL:
        return _cache["data"]

    items = []
    for source, url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:15]:
                title   = entry.get("title", "").strip()
                summary = entry.get("summary", "")
                pub     = entry.get("published", "")
                link    = entry.get("link", "")

                if not title:
                    continue
                if not _is_gold_relevant(title + " " + summary):
                    continue

                score = _score(title + " " + summary)
                sentiment = "bullish" if score > 0 else "bearish" if score < 0 else "neutral"

                items.append({
                    "title":     title,
                    "source":    source,
                    "published": pub,
                    "link":      link,
                    "sentiment": sentiment,
                    "score":     score,
                })
        except Exception:
            continue

    if not items:
        result = {
            "bullish_pct": 50.0,
            "label":       "Netral",
            "news":        [],
            "fetched_at":  datetime.now().isoformat(),
        }
        _cache["data"] = result
        _cache["ts"]   = now
        return result

    bullish_count = sum(1 for i in items if i["sentiment"] == "bullish")
    bearish_count = sum(1 for i in items if i["sentiment"] == "bearish")
    total         = len(items)
    bullish_pct   = round(bullish_count / total * 100, 1)

    if bullish_pct >= 70:
        label = "Sangat Bullish"
    elif bullish_pct >= 55:
        label = "Bullish"
    elif bullish_pct >= 45:
        label = "Netral"
    elif bullish_pct >= 30:
        label = "Bearish"
    else:
        label = "Sangat Bearish"

    items.sort(key=lambda x: abs(x["score"]), reverse=True)

    result = {
        "bullish_pct": bullish_pct,
        "label":       label,
        "news":        items[:10],
        "fetched_at":  datetime.now().isoformat(),
    }

    _cache["data"] = result
    _cache["ts"]   = now
    return result
