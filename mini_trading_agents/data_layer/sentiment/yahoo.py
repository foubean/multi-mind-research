from __future__ import annotations

from typing import Any

from mini_trading_agents.data_layer.common import pct_change, yfinance_client
from mini_trading_agents.data_layer.lineage import make_lineage
from mini_trading_agents.data_layer.sentiment.base import SentimentDataAdapter


class YahooSentimentDataAdapter(SentimentDataAdapter):
    source_key = "yahoo"

    def fetch(self, ticker: str, as_of: str) -> dict[str, Any]:
        yf = yfinance_client()
        ticker_history = yf.Ticker(ticker).history(period="1mo", interval="1d", auto_adjust=False)
        vix_history = yf.Ticker("^VIX").history(period="1mo", interval="1d", auto_adjust=False)
        if ticker_history.empty:
            raise RuntimeError(f"Yahoo Finance returned no short-term history for {ticker}.")

        ticker_history = ticker_history.dropna(subset=["Close"])
        closes = [float(value) for value in ticker_history["Close"].tolist()]
        if len(closes) < 2:
            raise RuntimeError(f"Yahoo Finance short-term history for {ticker} is too short.")

        five_day_change = pct_change(closes[-1], closes[-6] if len(closes) >= 6 else closes[0])
        month_change = pct_change(closes[-1], closes[0])
        vix_close = _latest_vix_close(vix_history)
        sentiment_score = _sentiment_score_from_market_proxies(five_day_change, month_change, vix_close)

        return {
            "ticker": ticker,
            "as_of": as_of,
            "source": "yahoo_finance_market_proxies",
            "sentiment_score": round(sentiment_score, 4),
            "positive_mentions": max(0, int(1000 * (1 + max(sentiment_score, 0)))),
            "negative_mentions": max(0, int(1000 * (1 + max(-sentiment_score, 0)))),
            "neutral_mentions": 1000,
            "mention_change_pct_24h": round(five_day_change, 4),
            "top_topics": ["price momentum", "market volatility", "risk appetite"],
            "observations": [
                f"Five-day price change is {five_day_change:.2f}%.",
                f"One-month price change is {month_change:.2f}%.",
                f"VIX proxy is {vix_close:.2f}." if vix_close else "VIX proxy was unavailable from Yahoo.",
                "Sentiment is derived from market proxies, not social-media messages.",
            ],
            "lineage": make_lineage(
                provider="yahoo",
                adapter="YahooSentimentDataAdapter",
                raw_source="yfinance.Ticker.history for ticker and ^VIX",
                transforms=[
                    {"field": "mention_change_pct_24h", "derived_from": ["Close[-1]", "Close[-6]"], "method": "five-day pct_change proxy"},
                    {"field": "sentiment_score", "derived_from": ["five_day_change", "month_change", "vix_close"], "method": "market proxy scoring"},
                    {"field": "positive_mentions", "derived_from": ["sentiment_score"], "method": "synthetic mention estimate"},
                    {"field": "negative_mentions", "derived_from": ["sentiment_score"], "method": "synthetic mention estimate"},
                ],
                used_by="sentiment_analyst",
            ),
        }


def _latest_vix_close(vix_history: Any) -> float:
    if vix_history.empty:
        return 0.0
    cleaned_vix = vix_history.dropna(subset=["Close"])
    if cleaned_vix.empty:
        return 0.0
    return float(cleaned_vix["Close"].iloc[-1])


def _sentiment_score_from_market_proxies(five_day_change: float, month_change: float, vix_close: float) -> float:
    momentum_component = max(-0.6, min(0.6, (five_day_change + month_change / 2) / 20))
    if vix_close >= 30:
        volatility_component = -0.3
    elif vix_close >= 20:
        volatility_component = -0.1
    elif vix_close > 0:
        volatility_component = 0.1
    else:
        volatility_component = 0.0
    return max(-1.0, min(1.0, momentum_component + volatility_component))
