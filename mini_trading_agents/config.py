from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - for Python < 3.11
    import tomli as tomllib


DEFAULT_CONFIG_PATH = "conf/config.toml"


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


def load_config(path: str | None = DEFAULT_CONFIG_PATH) -> AppConfig:
    data: dict[str, Any] = {}
    if path:
        config_path = Path(path)
        if config_path.exists():
            with config_path.open("rb") as config_file:
                data = tomllib.load(config_file)

    persistence = data.get("persistence", {})
    return AppConfig(
        persistence=PersistenceConfig(
            checkpoint_enabled=_as_bool(persistence.get("checkpoint_enabled"), True),
            snapshot_enabled=_as_bool(persistence.get("snapshot_enabled"), True),
            decision_memory_enabled=_as_bool(persistence.get("decision_memory_enabled"), True),
            storage_path=str(persistence.get("storage_path", "storage/trading_agents.sqlite")),
            checkpoint_path=str(persistence.get("checkpoint_path", "storage/langgraph_checkpoints.sqlite")),
            memory_store_path=str(persistence.get("memory_store_path", "storage/langgraph_memory.sqlite")),
        )
    )


def _as_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)
