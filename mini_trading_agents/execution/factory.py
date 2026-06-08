from __future__ import annotations

import os

from mini_trading_agents.config import PaperTradingConfig
from mini_trading_agents.execution.alpaca_paper import AlpacaPaperAdapter
from mini_trading_agents.execution.base import ExecutionAdapter
from mini_trading_agents.execution.models import AlpacaPaperSettings


def build_execution_adapter(config: PaperTradingConfig) -> ExecutionAdapter:
    provider = config.provider.strip().lower()
    if provider == "alpaca":
        return AlpacaPaperAdapter(
            AlpacaPaperSettings(
                api_key=os.getenv("ALPACA_API_KEY", ""),
                api_secret=os.getenv("ALPACA_API_SECRET", ""),
                base_url=config.alpaca_base_url,
                allow_fractional=config.allow_fractional,
            )
        )
    raise ValueError(f"Unsupported paper trading provider: {config.provider}")
