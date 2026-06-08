from __future__ import annotations

from dataclasses import dataclass

from mini_trading_agents.data_layer.fundamentals.base import FundamentalsDataAdapter
from mini_trading_agents.data_layer.fundamentals.sample import SampleFundamentalsDataAdapter
from mini_trading_agents.data_layer.fundamentals.yahoo import YahooFundamentalsDataAdapter
from mini_trading_agents.data_layer.market.alpaca import AlpacaMarketDataAdapter
from mini_trading_agents.data_layer.market.base import MarketDataAdapter
from mini_trading_agents.data_layer.market.sample import SampleMarketDataAdapter
from mini_trading_agents.data_layer.market.yahoo import YahooMarketDataAdapter
from mini_trading_agents.data_layer.news.base import NewsDataAdapter
from mini_trading_agents.data_layer.news.sample import SampleNewsDataAdapter
from mini_trading_agents.data_layer.news.yahoo import YahooNewsDataAdapter
from mini_trading_agents.data_layer.sentiment.base import SentimentDataAdapter
from mini_trading_agents.data_layer.sentiment.sample import SampleSentimentDataAdapter
from mini_trading_agents.data_layer.sentiment.yahoo import YahooSentimentDataAdapter


@dataclass(frozen=True)
class DataAdapters:
    market: MarketDataAdapter
    sentiment: SentimentDataAdapter
    news: NewsDataAdapter
    fundamentals: FundamentalsDataAdapter


def get_data_adapters(provider_keys: dict[str, str], config: dict | None = None) -> DataAdapters:
    config = config or {}
    return DataAdapters(
        market=_build_adapter(provider_keys["market"], _MARKET_ADAPTERS, "market", config.get("market", {})),
        sentiment=_build_adapter(provider_keys["sentiment"], _SENTIMENT_ADAPTERS, "sentiment"),
        news=_build_adapter(provider_keys["news"], _NEWS_ADAPTERS, "news"),
        fundamentals=_build_adapter(provider_keys["fundamentals"], _FUNDAMENTALS_ADAPTERS, "fundamentals"),
    )


def _build_adapter(provider_key: str, adapters: dict[str, type], data_kind: str, config: dict | None = None):
    try:
        adapter_class = adapters[provider_key]
    except KeyError as exc:
        available = ", ".join(sorted(adapters))
        raise ValueError(f"Unsupported {data_kind} data provider '{provider_key}'. Available: {available}") from exc
    if config and provider_key == "alpaca":
        return adapter_class(config)
    return adapter_class()


_MARKET_ADAPTERS = {
    "alpaca": AlpacaMarketDataAdapter,
    "sample": SampleMarketDataAdapter,
    "yahoo": YahooMarketDataAdapter,
}

_SENTIMENT_ADAPTERS = {
    "sample": SampleSentimentDataAdapter,
    "yahoo": YahooSentimentDataAdapter,
}

_NEWS_ADAPTERS = {
    "sample": SampleNewsDataAdapter,
    "yahoo": YahooNewsDataAdapter,
}

_FUNDAMENTALS_ADAPTERS = {
    "sample": SampleFundamentalsDataAdapter,
    "yahoo": YahooFundamentalsDataAdapter,
}
