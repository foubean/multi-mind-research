from __future__ import annotations

from collections.abc import Callable
from typing import Any

from mini_trading_agents.data_layer.factory import get_data_adapters
from mini_trading_agents.state import TradingState


FetchFn = Callable[[str, str], dict[str, Any]]


def prepare_data(state: TradingState) -> dict[str, Any]:
    provider_keys = state["data_providers"]
    adapters = get_data_adapters(provider_keys, state.get("data_provider_config", {}))
    ticker = state["ticker"]
    as_of = state["analysis_date"]
    notes: list[str] = []

    market_data = _fetch_slice("market", provider_keys["market"], adapters.market.source_key, adapters.market.fetch, ticker, as_of, notes)
    sentiment_data = _fetch_slice(
        "sentiment",
        provider_keys["sentiment"],
        adapters.sentiment.source_key,
        adapters.sentiment.fetch,
        ticker,
        as_of,
        notes,
    )
    news_data = _fetch_slice("news", provider_keys["news"], adapters.news.source_key, adapters.news.fetch, ticker, as_of, notes)
    fundamentals_data = _fetch_slice(
        "fundamentals",
        provider_keys["fundamentals"],
        adapters.fundamentals.source_key,
        adapters.fundamentals.fetch,
        ticker,
        as_of,
        notes,
    )

    return {
        "market_data": market_data,
        "sentiment_data": sentiment_data,
        "news_data": news_data,
        "fundamentals_data": fundamentals_data,
        "data_status": {
            "providers": provider_keys,
            "status": _status_from_notes(notes),
            "notes": notes,
        },
    }


def _fetch_slice(
    data_kind: str,
    provider_key: str,
    source_key: str,
    fetch: FetchFn,
    ticker: str,
    as_of: str,
    notes: list[str],
) -> dict[str, Any]:
    try:
        data = fetch(ticker, as_of)
        notes.append(f"Fetched {data_kind} data from {source_key}.")
        return data
    except Exception as exc:
        if provider_key == "sample":
            raise
        notes.append(f"{provider_key} {data_kind} data fallback to sample: {exc}")
        return _sample_fetcher(data_kind)(ticker, as_of)


def _sample_fetcher(data_kind: str) -> FetchFn:
    adapters = get_data_adapters(
        {
            "market": "sample",
            "sentiment": "sample",
            "news": "sample",
            "fundamentals": "sample",
        }
    )
    fetchers: dict[str, FetchFn] = {
        "market": adapters.market.fetch,
        "sentiment": adapters.sentiment.fetch,
        "news": adapters.news.fetch,
        "fundamentals": adapters.fundamentals.fetch,
    }
    return fetchers[data_kind]


def _status_from_notes(notes: list[str]) -> str:
    if any("fallback" in note.lower() for note in notes):
        return "partial"
    return "ok"
