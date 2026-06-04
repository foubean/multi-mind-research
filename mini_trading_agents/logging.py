from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


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

    def stream_chunk(self, chunk: dict[str, Any]) -> None:
        self.event(
            "stream_chunk",
            stream_type=chunk.get("type"),
            namespace=chunk.get("ns", ()),
            data=chunk.get("data"),
        )


def make_log_path(log_dir: str | Path, ticker: str, analysis_date: str) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    safe_ticker = "".join(char for char in ticker.upper() if char.isalnum() or char in "._-")
    return Path(log_dir) / f"{safe_ticker}_{analysis_date}_{timestamp}.jsonl"
