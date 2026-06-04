from __future__ import annotations

from typing import Any

from mini_trading_agents.data_layer.market.base import MarketDataAdapter
from mini_trading_agents.data_layer.sample_loader import load_sample_data


class SampleMarketDataAdapter(MarketDataAdapter):
    source_key = "sample"

    def fetch(self, ticker: str, as_of: str) -> dict[str, Any]:
        return load_sample_data("market_data.sample.json", ticker, as_of)
