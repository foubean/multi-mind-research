from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class SqliteStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def create_or_update_run(self, run_id: str, state: dict[str, Any], status: str = "running") -> None:
        now = _now()
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
                    state["ticker"],
                    state["analysis_date"],
                    status,
                    now,
                    now,
                    _json(state),
                ),
            )

    def save_snapshot(self, run_id: str, step_index: int, state: dict[str, Any]) -> None:
        now = _now()
        node_name = state["trace"][-1] if state.get("trace") else "start"
        with self._connect() as conn:
            conn.execute(
                """
                insert into workflow_snapshots (run_id, step_index, node_name, state_json, created_at)
                values (?, ?, ?, ?, ?)
                """,
                (run_id, step_index, node_name, _json(state), now),
            )
            conn.execute(
                """
                update workflow_runs
                set status = ?, updated_at = ?, final_state_json = ?
                where run_id = ?
                """,
                ("running", now, _json(state), run_id),
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

    def mark_completed(self, run_id: str, state: dict[str, Any]) -> None:
        now = _now()
        with self._connect() as conn:
            conn.execute(
                """
                update workflow_runs
                set status = ?, updated_at = ?, final_state_json = ?
                where run_id = ?
                """,
                ("completed", now, _json(state), run_id),
            )

    def save_decision_memory(self, run_id: str, state: dict[str, Any]) -> None:
        decision = state.get("final_trade_decision")
        if not decision:
            return
        now = _now()
        memory_event = build_decision_memory_event(run_id, state)
        with self._connect() as conn:
            conn.execute(
                """
                insert into decision_memory (
                    run_id, ticker, analysis_date, final_action, confidence,
                    position_size, reason, decision_json, created_at
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    state["ticker"],
                    state["analysis_date"],
                    decision["action"],
                    decision["confidence"],
                    decision["position_size"],
                    decision["reason"],
                    _json(decision),
                    now,
                ),
            )
            conn.execute(
                """
                insert into memory_events (
                    run_id, event_type, scope_type, scope_id, ticker, analysis_date,
                    summary, metadata_json, event_json, created_at
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    memory_event["event_type"],
                    memory_event["scope_type"],
                    memory_event["scope_id"],
                    memory_event["ticker"],
                    memory_event["analysis_date"],
                    memory_event["summary"],
                    _json(memory_event["metadata"]),
                    _json(memory_event),
                    now,
                ),
            )

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
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

                create table if not exists decision_memory (
                    id integer primary key autoincrement,
                    run_id text not null,
                    ticker text not null,
                    analysis_date text not null,
                    final_action text not null,
                    confidence real not null,
                    position_size text not null,
                    reason text not null,
                    decision_json text not null,
                    created_at text not null
                );

                create index if not exists idx_decision_memory_ticker
                on decision_memory(ticker, created_at);

                create table if not exists memory_events (
                    id integer primary key autoincrement,
                    run_id text not null,
                    event_type text not null,
                    scope_type text not null,
                    scope_id text not null,
                    ticker text,
                    analysis_date text,
                    summary text not null,
                    metadata_json text not null,
                    event_json text not null,
                    created_at text not null,
                    foreign key(run_id) references workflow_runs(run_id)
                );

                create index if not exists idx_memory_events_scope
                on memory_events(scope_type, scope_id, created_at);

                create index if not exists idx_memory_events_ticker
                on memory_events(ticker, created_at);

                create table if not exists trade_outcomes (
                    id integer primary key autoincrement,
                    run_id text not null unique,
                    ticker text not null,
                    analysis_date text not null,
                    final_action text not null,
                    position_size text not null,
                    entry_price real,
                    exit_price real,
                    holding_days integer,
                    return_pct real,
                    max_drawdown_pct real,
                    reward real,
                    outcome text,
                    notes text,
                    outcome_json text,
                    created_at text not null,
                    updated_at text not null,
                    foreign key(run_id) references workflow_runs(run_id)
                );

                create index if not exists idx_trade_outcomes_ticker_date
                on trade_outcomes(ticker, analysis_date);
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn


def _json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def build_decision_memory_event(run_id: str, state: dict[str, Any]) -> dict[str, Any]:
    decision = state["final_trade_decision"]
    signals = {
        "market": _report_signal(state, "market_report"),
        "sentiment": _report_signal(state, "sentiment_report"),
        "news": _report_signal(state, "news_report"),
        "fundamentals": _report_signal(state, "fundamentals_report"),
    }
    metadata = {
        "run_id": run_id,
        "ticker": state["ticker"],
        "analysis_date": state["analysis_date"],
        "data_providers": state.get("data_providers", {}),
        "signals": signals,
        "risk_status": state.get("risk_assessment", {}).get("status"),
        "action": decision["action"],
        "position_size": decision["position_size"],
        "confidence": decision["confidence"],
    }
    return {
        "event_type": "decision_event",
        "scope_type": "ticker",
        "scope_id": state["ticker"],
        "ticker": state["ticker"],
        "analysis_date": state["analysis_date"],
        "summary": (
            f"{state['ticker']} {state['analysis_date']} "
            f"{decision['action']} {decision['position_size']} "
            f"confidence={decision['confidence']}"
        ),
        "metadata": metadata,
        "decision": decision,
    }


def _report_signal(state: dict[str, Any], key: str) -> str | None:
    report = state.get(key)
    if not report:
        return None
    return report.get("signal")
