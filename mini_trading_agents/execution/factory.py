from __future__ import annotations

import os

from mini_trading_agents.config import PaperTradingConfig
from mini_trading_agents.execution.alpaca_paper import AlpacaPaperAdapter
from mini_trading_agents.execution.base import ExecutionAdapter
from mini_trading_agents.execution.local_paper import LocalPaperAdapter
from mini_trading_agents.execution.models import AlpacaPaperSettings, PaperTradingSettings


def build_execution_adapter(
    config: PaperTradingConfig,
    *,
    storage_path: str,
) -> ExecutionAdapter:
    provider = config.provider.strip().lower()
    if provider == "local":
        return LocalPaperAdapter(
            storage_path,
            PaperTradingSettings(
                account_id=config.account_id,
                initial_cash=config.initial_cash,
                base_currency=config.base_currency,
                fee_rate=config.fee_rate,
                slippage_bps=config.slippage_bps,
                allow_fractional=config.allow_fractional,
            ),
        )
    if provider == "alpaca":
        return AlpacaPaperAdapter(
            AlpacaPaperSettings(
                api_key=config.alpaca_api_key or os.getenv(config.alpaca_api_key_env, ""),
                api_secret=config.alpaca_api_secret or os.getenv(config.alpaca_api_secret_env, ""),
                base_url=config.alpaca_base_url,
                allow_fractional=config.allow_fractional,
            )
        )
    raise ValueError(f"Unsupported paper trading provider: {config.provider}")
