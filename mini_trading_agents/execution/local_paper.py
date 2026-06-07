from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from mini_trading_agents.execution.models import PaperTradingSettings, TARGET_WEIGHTS


class LocalPaperAdapter:
    """Local long-only paper trading adapter backed by SQLite."""

    def __init__(self, storage_path: str | Path, settings: PaperTradingSettings) -> None:
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.settings = settings
        self._initialize()

    def apply_decision(self, run_id: str, state: dict[str, Any]) -> dict[str, Any]:
        decision = state.get("final_trade_decision")
        market = state.get("market_data")
        if not decision or not market:
            return self._empty_result(state, "skipped", "Missing final decision or market data.")

        ticker = state["ticker"].upper()
        last_price = float(market["close"])
        action = str(decision["action"]).upper()
        # The single-ticker graph treats position_size as conviction. The local
        # paper adapter maps it to a target weight only for demo execution.
        target_weight = _target_weight(action, str(decision.get("position_size", "none")))

        with self._connect() as conn:
            self._ensure_account(conn)
            existing = conn.execute(
                "select result_json from paper_orders where run_id = ? and account_id = ?",
                (run_id, self.settings.account_id),
            ).fetchone()
            if existing:
                result = json.loads(existing["result_json"])
                result["status"] = "duplicate"
                result["message"] = "Paper order for this run already exists; returning saved result."
                return result

            account = self._account(conn)
            position = self._position(conn, ticker)
            portfolio_equity = self._portfolio_equity(conn, last_price)
            target_value = portfolio_equity * target_weight
            current_value = position["quantity"] * last_price
            delta_value = target_value - current_value
            side = _side_from_delta(delta_value)
            quantity_delta = _quantity_from_delta(delta_value, last_price, self.settings.allow_fractional)

            if action == "HOLD" or quantity_delta == 0:
                result = self._result(
                    conn=conn,
                    state=state,
                    status="no_order",
                    action=action,
                    target_weight=target_weight,
                    quantity_delta=0.0,
                    fill_price=last_price,
                    fee=0.0,
                    message="No paper order generated.",
                )
                self._save_snapshot(conn, run_id, state, result)
                return result

            fill_price = _fill_price(last_price, side, self.settings.slippage_bps)
            gross = abs(quantity_delta) * fill_price
            fee = round(gross * self.settings.fee_rate, 6)
            cash_delta = -gross - fee if side == "BUY" else gross - fee

            if side == "BUY" and account["cash"] + cash_delta < -1e-6:
                quantity_delta = _quantity_from_delta(account["cash"] / (1 + self.settings.fee_rate), fill_price, self.settings.allow_fractional)
                gross = abs(quantity_delta) * fill_price
                fee = round(gross * self.settings.fee_rate, 6)
                cash_delta = -gross - fee

            if quantity_delta == 0:
                result = self._result(
                    conn=conn,
                    state=state,
                    status="rejected",
                    action=action,
                    target_weight=target_weight,
                    quantity_delta=0.0,
                    fill_price=last_price,
                    fee=0.0,
                    message="Order rejected because available cash or share rounding produced zero quantity.",
                )
                self._save_snapshot(conn, run_id, state, result)
                return result

            order_id = f"po_{uuid4().hex[:12]}"
            fill_id = f"pf_{uuid4().hex[:12]}"
            now = _now()
            self._insert_order(conn, order_id, run_id, state, side, action, target_weight, quantity_delta, result_json=None)
            realized_delta = self._apply_fill(conn, ticker, side, quantity_delta, fill_price, fee, cash_delta)
            conn.execute(
                "update paper_accounts set cash = cash + ?, updated_at = ? where account_id = ?",
                (cash_delta, now, self.settings.account_id),
            )
            conn.execute(
                """
                insert into paper_fills (
                    fill_id, order_id, account_id, ticker, side, quantity, fill_price,
                    gross_value, fee, realized_pnl_delta, created_at
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (fill_id, order_id, self.settings.account_id, ticker, side, abs(quantity_delta), fill_price, gross, fee, realized_delta, now),
            )
            result = self._result(
                conn=conn,
                state=state,
                status="filled",
                action=action,
                target_weight=target_weight,
                quantity_delta=quantity_delta if side == "BUY" else -abs(quantity_delta),
                fill_price=fill_price,
                fee=fee,
                message=f"Filled local paper {side} order.",
                order_id=order_id,
                fill_id=fill_id,
            )
            conn.execute(
                "update paper_orders set status = ?, result_json = ?, updated_at = ? where order_id = ?",
                ("filled", _json(result), now, order_id),
            )
            self._save_snapshot(conn, run_id, state, result)
            return result

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                create table if not exists paper_accounts (
                    account_id text primary key,
                    cash real not null,
                    base_currency text not null,
                    created_at text not null,
                    updated_at text not null
                );

                create table if not exists paper_positions (
                    account_id text not null,
                    ticker text not null,
                    quantity real not null,
                    average_cost real not null,
                    realized_pnl real not null default 0,
                    updated_at text not null,
                    primary key(account_id, ticker)
                );

                create table if not exists paper_orders (
                    order_id text primary key,
                    run_id text not null,
                    account_id text not null,
                    ticker text not null,
                    side text not null,
                    decision_action text not null,
                    target_weight real not null,
                    quantity real not null,
                    status text not null,
                    result_json text,
                    created_at text not null,
                    updated_at text not null,
                    unique(run_id, account_id)
                );

                create table if not exists paper_fills (
                    fill_id text primary key,
                    order_id text not null,
                    account_id text not null,
                    ticker text not null,
                    side text not null,
                    quantity real not null,
                    fill_price real not null,
                    gross_value real not null,
                    fee real not null,
                    realized_pnl_delta real not null,
                    created_at text not null
                );

                create table if not exists portfolio_snapshots (
                    id integer primary key autoincrement,
                    run_id text not null,
                    account_id text not null,
                    ticker text not null,
                    cash real not null,
                    equity real not null,
                    position_quantity real not null,
                    average_cost real not null,
                    last_price real not null,
                    market_value real not null,
                    unrealized_pnl real not null,
                    realized_pnl real not null,
                    snapshot_json text not null,
                    created_at text not null
                );
                """
            )

    def _ensure_account(self, conn: sqlite3.Connection) -> None:
        now = _now()
        conn.execute(
            """
            insert into paper_accounts (account_id, cash, base_currency, created_at, updated_at)
            values (?, ?, ?, ?, ?)
            on conflict(account_id) do nothing
            """,
            (self.settings.account_id, self.settings.initial_cash, self.settings.base_currency, now, now),
        )

    def _account(self, conn: sqlite3.Connection) -> sqlite3.Row:
        return conn.execute(
            "select * from paper_accounts where account_id = ?",
            (self.settings.account_id,),
        ).fetchone()

    def _position(self, conn: sqlite3.Connection, ticker: str) -> sqlite3.Row:
        row = conn.execute(
            "select * from paper_positions where account_id = ? and ticker = ?",
            (self.settings.account_id, ticker),
        ).fetchone()
        if row:
            return row
        now = _now()
        conn.execute(
            """
            insert into paper_positions (account_id, ticker, quantity, average_cost, realized_pnl, updated_at)
            values (?, ?, 0, 0, 0, ?)
            """,
            (self.settings.account_id, ticker, now),
        )
        return conn.execute(
            "select * from paper_positions where account_id = ? and ticker = ?",
            (self.settings.account_id, ticker),
        ).fetchone()

    def _portfolio_equity(self, conn: sqlite3.Connection, current_price: float) -> float:
        account = self._account(conn)
        rows = conn.execute(
            "select quantity from paper_positions where account_id = ?",
            (self.settings.account_id,),
        ).fetchall()
        market_value = sum(float(row["quantity"]) * current_price for row in rows)
        return float(account["cash"]) + market_value

    def _insert_order(
        self,
        conn: sqlite3.Connection,
        order_id: str,
        run_id: str,
        state: dict[str, Any],
        side: str,
        action: str,
        target_weight: float,
        quantity: float,
        result_json: str | None,
    ) -> None:
        now = _now()
        conn.execute(
            """
            insert into paper_orders (
                order_id, run_id, account_id, ticker, side, decision_action,
                target_weight, quantity, status, result_json, created_at, updated_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order_id,
                run_id,
                self.settings.account_id,
                state["ticker"].upper(),
                side,
                action,
                target_weight,
                abs(quantity),
                "submitted",
                result_json,
                now,
                now,
            ),
        )

    def _apply_fill(
        self,
        conn: sqlite3.Connection,
        ticker: str,
        side: str,
        quantity: float,
        fill_price: float,
        fee: float,
        cash_delta: float,
    ) -> float:
        position = self._position(conn, ticker)
        old_qty = float(position["quantity"])
        old_cost = float(position["average_cost"])
        old_realized = float(position["realized_pnl"])
        qty = abs(quantity)
        realized_delta = 0.0

        if side == "BUY":
            new_qty = old_qty + qty
            new_cost = ((old_qty * old_cost) + (qty * fill_price) + fee) / new_qty if new_qty else 0.0
        else:
            sell_qty = min(qty, old_qty)
            realized_delta = (fill_price - old_cost) * sell_qty - fee
            new_qty = max(0.0, old_qty - sell_qty)
            new_cost = old_cost if new_qty > 0 else 0.0

        conn.execute(
            """
            update paper_positions
            set quantity = ?, average_cost = ?, realized_pnl = ?, updated_at = ?
            where account_id = ? and ticker = ?
            """,
            (
                round(new_qty, 8),
                round(new_cost, 8),
                round(old_realized + realized_delta, 8),
                _now(),
                self.settings.account_id,
                ticker,
            ),
        )
        return round(realized_delta, 8)

    def _save_snapshot(self, conn: sqlite3.Connection, run_id: str, state: dict[str, Any], result: dict[str, Any]) -> None:
        now = _now()
        conn.execute(
            """
            insert into portfolio_snapshots (
                run_id, account_id, ticker, cash, equity, position_quantity,
                average_cost, last_price, market_value, unrealized_pnl,
                realized_pnl, snapshot_json, created_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                self.settings.account_id,
                state["ticker"].upper(),
                result["cash"],
                result["equity"],
                result["position_quantity"],
                result["average_cost"],
                result["fill_price"],
                result["market_value"],
                result["unrealized_pnl"],
                result["realized_pnl"],
                _json(result),
                now,
            ),
        )

    def _result(
        self,
        *,
        conn: sqlite3.Connection,
        state: dict[str, Any],
        status: str,
        action: str,
        target_weight: float,
        quantity_delta: float,
        fill_price: float,
        fee: float,
        message: str,
        order_id: str | None = None,
        fill_id: str | None = None,
    ) -> dict[str, Any]:
        self._ensure_account(conn)
        position = self._position(conn, state["ticker"].upper())
        account = self._account(conn)
        quantity = float(position["quantity"])
        average_cost = float(position["average_cost"])
        market_value = quantity * fill_price
        unrealized = (fill_price - average_cost) * quantity if quantity else 0.0
        realized = float(position["realized_pnl"])
        cash = float(account["cash"])
        result = {
            "account_id": self.settings.account_id,
            "status": status,
            "action": action,
            "ticker": state["ticker"].upper(),
            "target_weight": round(target_weight, 4),
            "quantity_delta": round(quantity_delta, 8),
            "fill_price": round(fill_price, 4),
            "fee": round(fee, 6),
            "cash": round(cash, 4),
            "equity": round(cash + market_value, 4),
            "position_quantity": round(quantity, 8),
            "average_cost": round(average_cost, 4),
            "market_value": round(market_value, 4),
            "unrealized_pnl": round(unrealized, 4),
            "realized_pnl": round(realized, 4),
            "message": message,
        }
        if order_id:
            result["order_id"] = order_id
        if fill_id:
            result["fill_id"] = fill_id
        return result

    def _empty_result(self, state: dict[str, Any], status: str, message: str) -> dict[str, Any]:
        return {
            "account_id": self.settings.account_id,
            "status": status,
            "action": "N/A",
            "ticker": state.get("ticker", "N/A"),
            "target_weight": 0.0,
            "quantity_delta": 0.0,
            "fill_price": 0.0,
            "fee": 0.0,
            "cash": 0.0,
            "equity": 0.0,
            "position_quantity": 0.0,
            "average_cost": 0.0,
            "market_value": 0.0,
            "unrealized_pnl": 0.0,
            "realized_pnl": 0.0,
            "message": message,
        }

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.storage_path)
        conn.row_factory = sqlite3.Row
        return conn


def _target_weight(action: str, position_size: str) -> float:
    if action == "SELL":
        return 0.0
    if action == "HOLD":
        return TARGET_WEIGHTS.get(position_size, 0.0)
    return TARGET_WEIGHTS.get(position_size, 0.0)


def _side_from_delta(delta_value: float) -> str:
    return "BUY" if delta_value > 0 else "SELL"


def _quantity_from_delta(delta_value: float, price: float, allow_fractional: bool) -> float:
    if price <= 0:
        return 0.0
    quantity = abs(delta_value) / price
    if not allow_fractional:
        quantity = float(int(quantity))
    return round(quantity, 8)


def _fill_price(last_price: float, side: str, slippage_bps: float) -> float:
    multiplier = 1 + slippage_bps / 10000 if side == "BUY" else 1 - slippage_bps / 10000
    return round(last_price * multiplier, 4)


def _json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _now() -> str:
    return datetime.now(UTC).isoformat()
