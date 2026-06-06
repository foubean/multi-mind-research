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


def load_config(path: str | None = DEFAULT_CONFIG_PATH) -> AppConfig:
    data: dict[str, Any] = {}
    if path:
        config_path = Path(path)
        if config_path.exists():
            with config_path.open("rb") as config_file:
                data = tomllib.load(config_file)

    persistence = data.get("persistence", {})
    llm = _resolve_llm_config(data)
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
