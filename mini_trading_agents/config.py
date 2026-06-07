from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - for Python < 3.11
    import tomli as tomllib


DEFAULT_CONFIG_PATH = "config.toml"


@dataclass(frozen=True)
class PersistenceConfig:
    checkpoint_enabled: bool = True
    snapshot_enabled: bool = True
    decision_memory_enabled: bool = True
    storage_path: str = "storage/trading_agents.sqlite"
    checkpoint_path: str = "storage/langgraph_checkpoints.sqlite"
    memory_store_path: str = "storage/langgraph_memory.sqlite"


@dataclass(frozen=True)
class AppConfig:
    persistence: PersistenceConfig
    llm: "LLMConfig"
    paper_trading: "PaperTradingConfig"
    parameters: "ParameterConfig"
    trade_preferences: "TradePreferencesConfig"


@dataclass(frozen=True)
class LLMConfig:
    enabled: bool = False
    runtime_check_enabled: bool = True
    provider: str = "openai"
    model: str = ""
    api_key: str = ""
    api_key_env: str = "OPENAI_API_KEY"
    base_url: str = ""
    temperature: float = 0.2


@dataclass(frozen=True)
class PaperTradingConfig:
    enabled: bool = False
    provider: str = "local"
    account_id: str = "demo"
    initial_cash: float = 100000.0
    base_currency: str = "USD"
    fee_rate: float = 0.0005
    slippage_bps: float = 5.0
    allow_fractional: bool = True
    alpaca_api_key: str = ""
    alpaca_api_key_env: str = "ALPACA_API_KEY"
    alpaca_api_secret: str = ""
    alpaca_api_secret_env: str = "ALPACA_API_SECRET"
    alpaca_base_url: str = "https://paper-api.alpaca.markets"


@dataclass(frozen=True)
class ParameterConfig:
    scope: str = "node"


@dataclass(frozen=True)
class TradePreferencesConfig:
    risk_profile: str = "balanced"
    trading_style: str = "staged"
    target_return_pct: float = 0.12
    max_drawdown_pct: float = 0.08
    expected_holding_days: int = 20


def load_config(path: str | None = DEFAULT_CONFIG_PATH) -> AppConfig:
    data: dict[str, Any] = {}
    if path:
        config_path = Path(path)
        if config_path.exists():
            with config_path.open("rb") as config_file:
                data = tomllib.load(config_file)

    persistence = data.get("persistence", {})
    llm = _resolve_llm_config(data)
    paper_trading = data.get("paper_trading", {})
    parameters = data.get("parameters", {})
    trade_preferences = data.get("trade_preferences", {})
    return AppConfig(
        persistence=PersistenceConfig(
            checkpoint_enabled=_as_bool(persistence.get("checkpoint_enabled"), True),
            snapshot_enabled=_as_bool(persistence.get("snapshot_enabled"), True),
            decision_memory_enabled=_as_bool(persistence.get("decision_memory_enabled"), True),
            storage_path=str(persistence.get("storage_path", "storage/trading_agents.sqlite")),
            checkpoint_path=str(persistence.get("checkpoint_path", "storage/langgraph_checkpoints.sqlite")),
            memory_store_path=str(persistence.get("memory_store_path", "storage/langgraph_memory.sqlite")),
        ),
        llm=LLMConfig(
            enabled=_as_bool(llm.get("enabled"), False),
            runtime_check_enabled=_as_bool(llm.get("runtime_check_enabled"), True),
            provider=str(llm.get("provider", "openai")),
            model=str(llm.get("model", "")),
            api_key=str(llm.get("api_key", "")),
            api_key_env=str(llm.get("api_key_env", "OPENAI_API_KEY")),
            base_url=str(llm.get("base_url", "")),
            temperature=float(llm.get("temperature", 0.2)),
        ),
        paper_trading=PaperTradingConfig(
            enabled=_as_bool(paper_trading.get("enabled"), False),
            provider=str(paper_trading.get("provider", "local")),
            account_id=str(paper_trading.get("account_id", "demo")),
            initial_cash=float(paper_trading.get("initial_cash", 100000.0)),
            base_currency=str(paper_trading.get("base_currency", "USD")),
            fee_rate=float(paper_trading.get("fee_rate", 0.0005)),
            slippage_bps=float(paper_trading.get("slippage_bps", 5.0)),
            allow_fractional=_as_bool(paper_trading.get("allow_fractional"), True),
            alpaca_api_key=str(paper_trading.get("alpaca", {}).get("api_key", "")),
            alpaca_api_key_env=str(paper_trading.get("alpaca", {}).get("api_key_env", "ALPACA_API_KEY")),
            alpaca_api_secret=str(paper_trading.get("alpaca", {}).get("api_secret", "")),
            alpaca_api_secret_env=str(paper_trading.get("alpaca", {}).get("api_secret_env", "ALPACA_API_SECRET")),
            alpaca_base_url=str(paper_trading.get("alpaca", {}).get("base_url", "https://paper-api.alpaca.markets")),
        ),
        parameters=ParameterConfig(
            scope=str(parameters.get("scope", "node")),
        ),
        trade_preferences=TradePreferencesConfig(
            risk_profile=str(trade_preferences.get("risk_profile", "balanced")),
            trading_style=str(trade_preferences.get("trading_style", "staged")),
            target_return_pct=float(trade_preferences.get("target_return_pct", 0.12)),
            max_drawdown_pct=float(trade_preferences.get("max_drawdown_pct", 0.08)),
            expected_holding_days=int(trade_preferences.get("expected_holding_days", 20)),
        ),
    )


def _resolve_llm_config(data: dict[str, Any]) -> dict[str, Any]:
    if "llm" in data:
        return data["llm"]

    provider_name = data.get("model_provider")
    if not provider_name:
        return {}

    provider = data.get("model_providers", {}).get(provider_name, {})
    provider_key = str(provider.get("name", provider_name)).lower()
    return {
        "enabled": True,
        "runtime_check_enabled": data.get("runtime_check_enabled", True),
        "provider": provider_key,
        "model": data.get("model", ""),
        "api_key": provider.get("api_key", ""),
        "api_key_env": provider.get("api_key_env", "OPENAI_API_KEY"),
        "base_url": provider.get("base_url", ""),
        "temperature": data.get("temperature", 0.2),
    }


def _as_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)
