from __future__ import annotations

from typing import Any

from mini_trading_agents.data_layer.common import yfinance_client
from mini_trading_agents.data_layer.news.base import NewsDataAdapter


class YahooNewsDataAdapter(NewsDataAdapter):
    source_key = "yahoo"

    def fetch(self, ticker: str, as_of: str) -> dict[str, Any]:
        yf = yfinance_client()
        raw_news = yf.Ticker(ticker).news
        if not raw_news:
            raise RuntimeError(f"Yahoo Finance returned no news for {ticker}.")

        items = []
        for item in raw_news[:10]:
            content = item.get("content", item)
            title = content.get("title") or item.get("title") or "Untitled Yahoo Finance item"
            summary = content.get("summary") or content.get("description") or title
            provider = content.get("provider", {})
            source = provider.get("displayName") or item.get("publisher") or "Yahoo Finance"
            url = _extract_news_url(content) or item.get("link") or ""
            items.append(
                {
                    "title": title,
                    "source": source,
                    "published_at": _extract_published_at(content, item),
                    "summary": summary,
                    "url": url,
                    "sentiment": _rough_news_sentiment(title, summary),
                }
            )

        if not items:
            raise RuntimeError(f"Yahoo Finance news for {ticker} did not contain usable items.")

        positive = sum(1 for item in items if item["sentiment"] == "positive")
        negative = sum(1 for item in items if item["sentiment"] == "negative")
        return {
            "ticker": ticker,
            "as_of": as_of,
            "source": "yahoo_finance_news",
            "items": items,
            "observations": [
                f"Yahoo Finance returned {len(items)} recent news items.",
                f"Rough keyword sentiment count: {positive} positive, {negative} negative.",
                "News sentiment is a lightweight keyword heuristic until an LLM/news sentiment model is added.",
            ],
        }


def _extract_news_url(content: dict[str, Any]) -> str:
    canonical_url = content.get("canonicalUrl") or {}
    click_url = content.get("clickThroughUrl") or {}
    return canonical_url.get("url") or click_url.get("url") or ""


def _extract_published_at(content: dict[str, Any], item: dict[str, Any]) -> str:
    return content.get("pubDate") or content.get("displayTime") or str(item.get("providerPublishTime") or "")


def _rough_news_sentiment(title: str, summary: str) -> str:
    text = f"{title} {summary}".lower()
    positive_words = ["beat", "beats", "growth", "surge", "record", "raises", "upgrade", "partnership", "profit"]
    negative_words = ["miss", "falls", "drop", "lawsuit", "probe", "downgrade", "weak", "risk", "loss"]
    positive = sum(1 for word in positive_words if word in text)
    negative = sum(1 for word in negative_words if word in text)
    if positive > negative:
        return "positive"
    if negative > positive:
        return "negative"
    return "neutral"
