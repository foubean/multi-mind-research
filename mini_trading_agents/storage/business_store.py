from __future__ import annotations

from pathlib import Path
from typing import Any

from mini_trading_agents.storage.base import BaseSqliteStore, now_iso, to_json


BUSINESS_SCHEMA = """
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


class BusinessStore(BaseSqliteStore):
    def __init__(self, path: str | Path) -> None:
        super().__init__(path)

    def save_decision_memory(self, run_id: str, state: dict[str, Any]) -> None:
        decision = state.get("final_trade_decision")
        if not decision:
            return
        now = now_iso()
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
                    to_json(decision),
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
                    to_json(memory_event["metadata"]),
                    to_json(memory_event),
                    now,
                ),
            )

    def save_portfolio_memory(self, run_id: str, state: dict[str, Any]) -> None:
        plan = state.get("portfolio_plan")
        if not plan:
            return
        now = now_iso()
        memory_event = build_portfolio_memory_event(run_id, state)
        with self._connect() as conn:
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
                    None,
                    memory_event["analysis_date"],
                    memory_event["summary"],
                    to_json(memory_event["metadata"]),
                    to_json(memory_event),
                    now,
                ),
            )

    def save_trade_outcomes_from_paper_execution(self, run_id: str, state: dict[str, Any]) -> None:
        execution = state.get("paper_trading_result") or {}
        orders = execution.get("orders", [])
        if not orders:
            return
        now = now_iso()
        with self._connect() as conn:
            for order in orders:
                if order.get("status") not in {"filled", "submitted", "accepted", "pending_new", "new"}:
                    continue
                ticker = str(order.get("ticker", "")).upper()
                outcome_run_id = f"{run_id}:{ticker}"
                outcome_json = {
                    "portfolio_run_id": run_id,
                    "ticker": ticker,
                    "provider": execution.get("provider"),
                    "order_id": order.get("order_id"),
                    "fill_id": order.get("fill_id"),
                    "target_weight": order.get("target_weight"),
                    "actual_weight": order.get("actual_weight"),
                    "quantity": order.get("position_quantity"),
                    "quantity_delta": order.get("quantity_delta"),
                    "status": order.get("status"),
                    "paper_order": order,
                }
                conn.execute(
                    """
                    insert into trade_outcomes (
                        run_id, ticker, analysis_date, final_action, position_size,
                        entry_price, holding_days, return_pct, max_drawdown_pct,
                        reward, outcome, notes, outcome_json, created_at, updated_at
                    )
                    values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    on conflict(run_id) do update set
                        entry_price = excluded.entry_price,
                        outcome = excluded.outcome,
                        notes = excluded.notes,
                        outcome_json = excluded.outcome_json,
                        updated_at = excluded.updated_at
                    """,
                    (
                        outcome_run_id,
                        ticker,
                        state["analysis_date"],
                        str(order.get("side", "BUY")).upper(),
                        "portfolio_target",
                        order.get("fill_price"),
                        0,
                        None,
                        None,
                        None,
                        "open",
                        "Opened or updated from portfolio paper execution.",
                        to_json(outcome_json),
                        now,
                        now,
                    ),
                )

    def _initialize(self) -> None:
        super()._initialize()
        with self._connect() as conn:
            conn.executescript(BUSINESS_SCHEMA)


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
        "trade_advice": state.get("trade_advice"),
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


def build_portfolio_memory_event(run_id: str, state: dict[str, Any]) -> dict[str, Any]:
    plan = state["portfolio_plan"]
    metadata = {
        "run_id": run_id,
        "analysis_date": state["analysis_date"],
        "tickers": state.get("tickers", []),
        "target_weights": plan.get("target_weights", {}),
        "validation_result": state.get("validation_result"),
        "execution_validation_result": state.get("execution_validation_result"),
        "portfolio_risk_review": state.get("portfolio_risk_review"),
    }
    return {
        "event_type": "portfolio_decision_event",
        "scope_type": "portfolio",
        "scope_id": "global",
        "ticker": None,
        "analysis_date": state["analysis_date"],
        "summary": (
            f"Portfolio {state['analysis_date']} {plan.get('decision', 'N/A')} "
            f"tickers={','.join(state.get('tickers', []))}"
        ),
        "metadata": metadata,
        "portfolio_plan": plan,
    }


def _report_signal(state: dict[str, Any], key: str) -> str | None:
    report = state.get(key)
    if not report:
        return None
    return report.get("signal")
