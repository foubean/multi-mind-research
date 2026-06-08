from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mini_trading_agents.storage.base import BaseSqliteStore, now_iso, to_json


SNAPSHOT_SCHEMA = """
create table if not exists workflow_snapshots (
    id integer primary key autoincrement,
    run_id text not null,
    step_index integer not null,
    node_name text not null,
    state_json text not null,
    created_at text not null,
    foreign key(run_id) references workflow_runs(run_id)
);

create index if not exists idx_workflow_snapshots_run_step
on workflow_snapshots(run_id, step_index);
"""


class SnapshotStore(BaseSqliteStore):
    def __init__(self, path: str | Path) -> None:
        super().__init__(path)

    def save_snapshot(self, run_id: str, step_index: int, state: dict[str, Any]) -> None:
        now = now_iso()
        node_name = state["trace"][-1] if state.get("trace") else "start"
        with self._connect() as conn:
            conn.execute(
                """
                insert into workflow_snapshots (run_id, step_index, node_name, state_json, created_at)
                values (?, ?, ?, ?, ?)
                """,
                (run_id, step_index, node_name, to_json(state), now),
            )
            conn.execute(
                """
                update workflow_runs
                set status = ?, updated_at = ?, final_state_json = ?
                where run_id = ?
                """,
                ("running", now, to_json(state), run_id),
            )

    def latest_snapshot(self, run_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                select state_json
                from workflow_snapshots
                where run_id = ?
                order by step_index desc, id desc
                limit 1
                """,
                (run_id,),
            ).fetchone()
        if not row:
            return None
        return json.loads(row["state_json"])

    def _initialize(self) -> None:
        super()._initialize()
        with self._connect() as conn:
            conn.executescript(SNAPSHOT_SCHEMA)
