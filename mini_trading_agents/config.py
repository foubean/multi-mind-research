from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date
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
    snapshot_path: str = "storage/workflow_snapshots.sqlite"
    storage_path: str = "storage/trading_agents.sqlite"
    checkpoint_path: str = "storage/langgraph_checkpoints.sqlite"
    memory_store_path: str = "storage/langgraph_memory.sqlite"


@dataclass(frozen=True)
class AppConfig:
    persistence: PersistenceConfig
    llm: "LLMConfig"
    paper_trading: "PaperTradingConfig"
    run: "RunConfig"
    data_providers: "DataProviderConfig"
    logging: "LoggingConfig"
    reporting: "ReportingConfig"
    portfolio: "PortfolioConfig"
    trade_preferences: "TradePreferencesConfig"


@dataclass(frozen=True)
class LLMConfig:
    enabled: bool = True
    provider: str = "openai"
    model: str = ""
    api_key: str = ""
    api_key_env: str = "OPENAI_API_KEY"
    base_url: str = ""


@dataclass(frozen=True)
class PaperTradingConfig:
    enable: bool = False
    provider: str = "alpaca"
    allow_fractional: bool = True
    alpaca_base_url: str = "https://paper-api.alpaca.markets"


@dataclass(frozen=True)
class RunConfig:
    tickers: tuple[str, ...] = ("NVDA", "AAPL", "MSFT")
    analysis_date: str = ""
    research_turns: int = 4
    risk_turns: int = 6
    max_parallel_tickers: int = 5


@dataclass(frozen=True)
class DataProviderConfig:
    default: str = "sample"
    market: str = ""
    sentiment: str = ""
    news: str = ""
    fundamentals: str = ""


@dataclass(frozen=True)
class LoggingConfig:
    log_enabled: bool = True
    log_dir: str = "logs"


@dataclass(frozen=True)
class ReportingConfig:
    report_dir: str = "reports"


@dataclass(frozen=True)
class PortfolioConstraintsConfig:
    long_only: bool = True
    allow_fractional: bool = True
    max_tickers: int = 20
    max_single_position_pct: float = 0.25
    max_total_equity_pct: float = 0.85
    cash_reserve_pct: float = 0.05
    max_turnover_pct: float = 0.2
    max_sector_exposure_pct: float = 0.45
    max_theme_exposure_pct: float = 0.45
    max_correlation_cluster_pct: float = 0.5
    max_new_positions: int = 5
    min_order_value: float = 100.0
    cooldown_days_after_loss: int = 0
    no_trade_symbols: tuple[str, ...] = ()


@dataclass(frozen=True)
class PortfolioConfig:
    max_revision_count: int = 2
    single_ticker_failure_policy: str = "fail_fast"
    constraints: PortfolioConstraintsConfig = PortfolioConstraintsConfig()


@dataclass(frozen=True)
class TradePreferencesConfig:
    preferences_path: str = "config/trade_preferences.default.json"
    risk_profile: str = "balanced"
    trading_style: str = "staged"
    target_return_pct: float = 0.12
    max_drawdown_pct: float = 0.08
    expected_holding_days: int = 20


def load_config(path: str | None = DEFAULT_CONFIG_PATH) -> AppConfig:
    data: dict[str, Any] = {}
    config_path: Path | None = None
    if path:
        config_path = Path(path)
        _load_secret_env_files(config_path.parent)
        if config_path.exists():
            with config_path.open("rb") as config_file:
                data = tomllib.load(config_file)
    else:
        _load_secret_env_files(Path("."))

    persistence = data.get("persistence", {})
    llm = _resolve_llm_config(data)
    paper_trading = data.get("paper_trading", {})
    run = data.get("run", {})
    data_providers = data.get("data_providers", {})
    logging_config = data.get("logging", {})
    reporting = data.get("reporting", {})
    config_files = data.get("config_files", {})
    portfolio = data.get("portfolio", {})
    constraints_path = str(config_files.get("constraints_path", "config/portfolio_constraints.default.json"))
    portfolio_constraints = _load_portfolio_constraints(config_path, constraints_path)
    portfolio_constraints.update(portfolio.get("constraints", {}))
    trade_preferences_path = str(config_files.get("trade_preferences_path", "config/trade_preferences.default.json"))
    trade_preferences = _load_json_object(config_path, trade_preferences_path, "trade preferences")
    trade_preferences.update(data.get("trade_preferences", {}))
    return AppConfig(
        persistence=PersistenceConfig(
            checkpoint_enabled=_as_bool(persistence.get("checkpoint_enabled"), True),
            snapshot_enabled=_as_bool(persistence.get("snapshot_enabled"), True),
            decision_memory_enabled=_as_bool(persistence.get("decision_memory_enabled"), True),
            snapshot_path=str(persistence.get("snapshot_path", "storage/workflow_snapshots.sqlite")),
            storage_path=str(persistence.get("storage_path", "storage/trading_agents.sqlite")),
            checkpoint_path=str(persistence.get("checkpoint_path", "storage/langgraph_checkpoints.sqlite")),
            memory_store_path=str(persistence.get("memory_store_path", "storage/langgraph_memory.sqlite")),
        ),
        llm=LLMConfig(
            enabled=True,
            provider=str(llm.get("provider", "openai")),
            model=str(llm.get("model", "")),
            api_key=str(llm.get("api_key", "")),
            api_key_env=str(llm.get("api_key_env", "OPENAI_API_KEY")),
            base_url=str(llm.get("base_url", "")) or os.getenv("OPENAI_BASE_URL", ""),
        ),
        paper_trading=PaperTradingConfig(
            enable=_as_bool(paper_trading.get("enable"), False),
            provider=str(paper_trading.get("provider", "alpaca")),
            allow_fractional=_as_bool(paper_trading.get("allow_fractional"), True),
            alpaca_base_url=os.getenv("ALPACA_PAPER_BASE_URL", "https://paper-api.alpaca.markets"),
        ),
        run=RunConfig(
            tickers=_as_ticker_tuple(run.get("tickers", ["NVDA", "AAPL", "MSFT"])),
            analysis_date=_resolve_analysis_date(str(run.get("analysis_date", ""))),
            research_turns=int(run.get("research_turns", 4)),
            risk_turns=int(run.get("risk_turns", 6)),
            max_parallel_tickers=int(run.get("max_parallel_tickers", 5)),
        ),
        data_providers=DataProviderConfig(
            default=str(data_providers.get("default", "sample")),
            market=str(data_providers.get("market", "")),
            sentiment=str(data_providers.get("sentiment", "")),
            news=str(data_providers.get("news", "")),
            fundamentals=str(data_providers.get("fundamentals", "")),
        ),
        reporting=ReportingConfig(
            report_dir=str(reporting.get("report_dir", "reports")),
        ),
        logging=LoggingConfig(
            log_enabled=_as_bool(logging_config.get("enabled"), True),
            log_dir=str(logging_config.get("log_dir", "logs")),
        ),
        portfolio=PortfolioConfig(
            max_revision_count=int(portfolio.get("max_revision_count", 2)),
            single_ticker_failure_policy=str(portfolio.get("single_ticker_failure_policy", "fail_fast")),
            constraints=PortfolioConstraintsConfig(
                long_only=_as_bool(portfolio_constraints.get("long_only"), True),
                allow_fractional=_as_bool(portfolio_constraints.get("allow_fractional"), True),
                max_tickers=int(portfolio_constraints.get("max_tickers", 20)),
                max_single_position_pct=float(portfolio_constraints.get("max_single_position_pct", 0.25)),
                max_total_equity_pct=float(portfolio_constraints.get("max_total_equity_pct", 0.85)),
                cash_reserve_pct=float(portfolio_constraints.get("cash_reserve_pct", 0.05)),
                max_turnover_pct=float(portfolio_constraints.get("max_turnover_pct", 0.2)),
                max_sector_exposure_pct=float(portfolio_constraints.get("max_sector_exposure_pct", 0.45)),
                max_theme_exposure_pct=float(portfolio_constraints.get("max_theme_exposure_pct", 0.45)),
                max_correlation_cluster_pct=float(portfolio_constraints.get("max_correlation_cluster_pct", 0.5)),
                max_new_positions=int(portfolio_constraints.get("max_new_positions", 5)),
                min_order_value=float(portfolio_constraints.get("min_order_value", 100.0)),
                cooldown_days_after_loss=int(portfolio_constraints.get("cooldown_days_after_loss", 0)),
                no_trade_symbols=tuple(
                    str(symbol).upper() for symbol in portfolio_constraints.get("no_trade_symbols", [])
                ),
            ),
        ),
        trade_preferences=TradePreferencesConfig(
            preferences_path=trade_preferences_path,
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
        "provider": provider_key,
        "model": data.get("model", ""),
        "api_key": provider.get("api_key", ""),
        "api_key_env": provider.get("api_key_env", "OPENAI_API_KEY"),
        "base_url": provider.get("base_url", "") or os.getenv("OPENAI_BASE_URL", ""),
    }


def _load_secret_env_files(directory: Path) -> None:
    _load_env_file(directory / ".env.openai")
    _load_env_file(directory / ".env.alpaca")


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = _strip_env_value(value.strip())
        if key:
            os.environ[key] = value


def _strip_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _load_portfolio_constraints(config_path: Path | None, constraints_path: str) -> dict[str, Any]:
    return _load_json_object(config_path, constraints_path, "portfolio constraints")


def _load_json_object(config_path: Path | None, json_path: str, label: str) -> dict[str, Any]:
    path = Path(json_path)
    if not path.is_absolute() and config_path is not None:
        path = config_path.parent / path
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as json_file:
        data = json.load(json_file)
    if not isinstance(data, dict):
        raise ValueError(f"{label} file must contain a JSON object: {path}")
    return data


def _as_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _as_ticker_tuple(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        items = value.split(",")
    else:
        items = value
    tickers = tuple(str(ticker).strip().upper() for ticker in items if str(ticker).strip())
    return tickers or ("NVDA", "AAPL", "MSFT")


def _resolve_analysis_date(value: str) -> str:
    value = value.strip()
    return value or date.today().isoformat()
