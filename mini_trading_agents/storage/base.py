from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


RUN_SCHEMA = """
create table if not exists workflow_runs (
    run_id text primary key,
    ticker text not null,
    analysis_date text not null,
    status text not null,
    created_at text not null,
    updated_at text not null,
    initial_state_json text not null,
    final_state_json text
);
"""


class BaseSqliteStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def create_or_update_run(self, run_id: str, state: dict[str, Any], status: str = "running") -> None:
        now = now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                insert into workflow_runs (
                    run_id, ticker, analysis_date, status, created_at, updated_at, initial_state_json
                )
                values (?, ?, ?, ?, ?, ?, ?)
                on conflict(run_id) do update set
                    ticker = excluded.ticker,
                    analysis_date = excluded.analysis_date,
                    status = excluded.status,
                    updated_at = excluded.updated_at
                """,
                (
                    run_id,
                    state.get("ticker", "PORTFOLIO"),
                    state["analysis_date"],
                    status,
                    now,
                    now,
                    to_json(state),
                ),
            )

    def mark_completed(self, run_id: str, state: dict[str, Any]) -> None:
        now = now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                update workflow_runs
                set status = ?, updated_at = ?, final_state_json = ?
                where run_id = ?
                """,
                ("completed", now, to_json(state), run_id),
            )

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(RUN_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn


def to_json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def now_iso() -> str:
    return datetime.now(UTC).isoformat()
