from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mini_trading_agents.state import TradingState


class JsonlRunLogger:
    """Append-only JSONL logger for workflow audit trails."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def event(self, event_type: str, **payload: Any) -> None:
        record = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event": event_type,
            **payload,
        }
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")


def make_log_path(log_dir: str | Path, ticker: str, analysis_date: str) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    safe_ticker = "".join(char for char in ticker.upper() if char.isalnum() or char in "._-")
    return Path(log_dir) / f"{safe_ticker}_{analysis_date}_{timestamp}.jsonl"


def state_summary(state: TradingState) -> dict[str, Any]:
    return {
        "ticker": state["ticker"],
        "analysis_date": state["analysis_date"],
        "trace": list(state["trace"]),
        "available_fields": sorted(state.keys()),
    }


def changed_keys(before: TradingState, updates: TradingState) -> list[str]:
    changed: list[str] = []
    for key, value in updates.items():
        if key not in before or before[key] != value:
            changed.append(key)
    return changed
