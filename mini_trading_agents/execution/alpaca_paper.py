from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from mini_trading_agents.execution.models import AlpacaPaperSettings, TARGET_WEIGHTS, latest_prices_from_portfolio_state


class AlpacaPaperAdapter:
    """Alpaca paper trading adapter using the official REST API shape."""

    def __init__(self, settings: AlpacaPaperSettings) -> None:
        if not settings.api_key or not settings.api_secret:
            raise RuntimeError("Alpaca paper trading requires API key and secret.")
        self.settings = settings
        self.base_url = settings.base_url.rstrip("/")

    def get_account_context(self) -> dict[str, Any]:
        account = self._request("GET", "/v2/account")
        positions = self._request("GET", "/v2/positions")
        if not isinstance(positions, list):
            positions = []
        equity = float(account.get("equity", account.get("portfolio_value", 0)) or 0)
        normalized_positions: dict[str, Any] = {}
        for item in positions:
            ticker = str(item.get("symbol", "")).upper()
            if not ticker:
                continue
            market_value = float(item.get("market_value", 0) or 0)
            normalized_positions[ticker] = {
                "quantity": float(item.get("qty", 0) or 0),
                "market_value": round(market_value, 6),
                "weight": round(market_value / equity, 6) if equity else 0.0,
                "unrealized_pnl": round(float(item.get("unrealized_pl", 0) or 0), 6),
                "average_cost": float(item.get("avg_entry_price", 0) or 0),
                "last_price": float(item.get("current_price", 0) or 0),
                "realized_pnl": 0.0,
            }
        history = self._portfolio_history()
        return {
            "account_id": str(account.get("account_number") or account.get("id") or "alpaca-paper"),
            "cash": round(float(account.get("cash", 0) or 0), 6),
            "equity": round(equity, 6),
            "base_currency": str(account.get("currency", "USD")),
            "positions": normalized_positions,
            "portfolio_history": history if isinstance(history, dict) else {},
            "source": "alpaca_paper_api",
        }

    def apply_decision(self, run_id: str, state: dict[str, Any]) -> dict[str, Any]:
        decision = state.get("final_trade_decision")
        market = state.get("market_data")
        if not decision or not market:
            return _empty_result(state, "skipped", "Missing final decision or market data.")

        ticker = state["ticker"].upper()
        action = str(decision["action"]).upper()
        # The single-ticker graph treats position_size as conviction. The paper
        # broker adapter maps it to a target weight only for single-ticker execution.
        target_weight = _target_weight(action, str(decision.get("position_size", "none")))
        account = self._request("GET", "/v2/account")
        current_position = self._position(ticker)
        last_price = float(market["close"])
        portfolio_value = float(account.get("portfolio_value") or account.get("equity") or 0)
        current_qty = float(current_position.get("qty", 0) or 0)
        current_value = current_qty * last_price
        target_value = portfolio_value * target_weight
        delta_value = target_value - current_value
        side = "buy" if delta_value > 0 else "sell"
        quantity = _quantity(abs(delta_value), last_price, self.settings.allow_fractional)

        if action == "HOLD" or quantity == 0:
            return self._result(
                state=state,
                account=account,
                position=current_position,
                status="no_order",
                action=action,
                target_weight=target_weight,
                quantity_delta=0.0,
                fill_price=last_price,
                message="No Alpaca paper order generated.",
            )

        client_order_id = _client_order_id(run_id, ticker)
        existing_order = self._order_by_client_order_id(client_order_id)
        if existing_order:
            refreshed_account = self._request("GET", "/v2/account")
            refreshed_position = self._position(ticker)
            history = self._portfolio_history()
            return self._result(
                state=state,
                account=refreshed_account,
                position=refreshed_position,
                status="duplicate",
                action=action,
                target_weight=target_weight,
                quantity_delta=0.0,
                fill_price=float(existing_order.get("filled_avg_price") or last_price),
                message="Alpaca paper order for this run already exists; returning broker order.",
                order_id=str(existing_order.get("id", "")),
                broker_order=existing_order,
                portfolio_history_points=len(history.get("timestamp", [])) if isinstance(history, dict) else 0,
            )
        order_payload = {
            "symbol": ticker,
            "side": side,
            "type": "market",
            "time_in_force": "day",
            "client_order_id": client_order_id,
        }
        if self.settings.allow_fractional:
            order_payload["qty"] = str(quantity)
        else:
            order_payload["qty"] = str(int(quantity))

        order = self._request("POST", "/v2/orders", order_payload)
        refreshed_account = self._request("GET", "/v2/account")
        refreshed_position = self._position(ticker)
        history = self._portfolio_history()
        return self._result(
            state=state,
            account=refreshed_account,
            position=refreshed_position,
            status=str(order.get("status", "submitted")),
            action=action,
            target_weight=target_weight,
            quantity_delta=quantity if side == "buy" else -quantity,
            fill_price=float(order.get("filled_avg_price") or last_price),
            message=f"Submitted Alpaca paper {side.upper()} order.",
            order_id=str(order.get("id", "")),
            broker_order=order,
            portfolio_history_points=len(history.get("timestamp", [])) if isinstance(history, dict) else 0,
        )

    def apply_portfolio_plan(self, run_id: str, state: dict[str, Any]) -> dict[str, Any]:
        execution_plan = state.get("execution_plan") or {}
        orders = execution_plan.get("orders", [])
        if not orders:
            account = self._request("GET", "/v2/account")
            return {
                "provider": "alpaca",
                "status": "no_order",
                "account_id": str(account.get("account_number") or account.get("id") or "alpaca-paper"),
                "orders": [],
                "message": "No Alpaca portfolio paper orders generated.",
            }
        account = self._request("GET", "/v2/account")
        prices = latest_prices_from_portfolio_state(state)
        results = []
        for order in orders:
            ticker = str(order["ticker"]).upper()
            price = prices.get(ticker)
            if not price:
                results.append(_portfolio_order_result(order, "skipped", "Missing latest price.", provider="alpaca"))
                continue
            results.append(self._submit_portfolio_order(run_id, account, order, ticker, price))
        refreshed_account = self._request("GET", "/v2/account")
        history = self._portfolio_history()
        return {
            "provider": "alpaca",
            "status": _portfolio_status(results),
            "account_id": str(refreshed_account.get("account_number") or refreshed_account.get("id") or "alpaca-paper"),
            "cash": round(float(refreshed_account.get("cash", 0) or 0), 4),
            "equity": round(float(refreshed_account.get("equity", refreshed_account.get("portfolio_value", 0)) or 0), 4),
            "portfolio_history_points": len(history.get("timestamp", [])) if isinstance(history, dict) else 0,
            "orders": results,
            "message": f"Processed {len(results)} Alpaca portfolio paper orders.",
        }

    def _submit_portfolio_order(
        self,
        run_id: str,
        account: dict[str, Any],
        order: dict[str, Any],
        ticker: str,
        last_price: float,
    ) -> dict[str, Any]:
        current_position = self._position(ticker)
        portfolio_value = float(account.get("portfolio_value") or account.get("equity") or 0)
        target_weight = float(order["target_weight"])
        target_value = portfolio_value * target_weight
        current_qty = float(current_position.get("qty", 0) or 0)
        current_value = current_qty * last_price
        delta_value = target_value - current_value
        side = "buy" if delta_value > 0 else "sell"
        quantity = _quantity(abs(delta_value), last_price, self.settings.allow_fractional)

        if quantity == 0:
            return _portfolio_order_result(order, "no_order", "Order delta is zero.", provider="alpaca")

        client_order_id = _client_order_id(run_id, ticker)
        existing_order = self._order_by_client_order_id(client_order_id)
        if existing_order:
            return _alpaca_portfolio_order_result(
                order=order,
                broker_order=existing_order,
                position=self._position(ticker),
                account=self._request("GET", "/v2/account"),
                status="duplicate",
                quantity_delta=0.0,
                fill_price=float(existing_order.get("filled_avg_price") or last_price),
                message="Alpaca portfolio paper order for this ticker/run already exists.",
            )

        order_payload = {
            "symbol": ticker,
            "side": side,
            "type": str(order.get("order_type", "market")),
            "time_in_force": str(order.get("time_in_force", "day")),
            "client_order_id": client_order_id,
        }
        if self.settings.allow_fractional:
            order_payload["qty"] = str(quantity)
        else:
            order_payload["qty"] = str(int(quantity))

        broker_order = self._request("POST", "/v2/orders", order_payload)
        return _alpaca_portfolio_order_result(
            order=order,
            broker_order=broker_order,
            position=self._position(ticker),
            account=self._request("GET", "/v2/account"),
            status=str(broker_order.get("status", "submitted")),
            quantity_delta=quantity if side == "buy" else -quantity,
            fill_price=float(broker_order.get("filled_avg_price") or last_price),
            message=f"Submitted Alpaca portfolio {side.upper()} order.",
        )

    def _position(self, ticker: str) -> dict[str, Any]:
        try:
            return self._request("GET", f"/v2/positions/{ticker}")
        except RuntimeError as exc:
            if "404" in str(exc):
                return {}
            raise

    def _portfolio_history(self) -> dict[str, Any]:
        try:
            return self._request("GET", "/v2/account/portfolio/history?period=1M&timeframe=1D")
        except RuntimeError:
            return {}

    def _order_by_client_order_id(self, client_order_id: str) -> dict[str, Any] | None:
        try:
            return self._request("GET", f"/v2/orders:by_client_order_id?client_order_id={quote(client_order_id)}")
        except RuntimeError as exc:
            if "404" in str(exc):
                return None
            raise

    def _result(
        self,
        *,
        state: dict[str, Any],
        account: dict[str, Any],
        position: dict[str, Any],
        status: str,
        action: str,
        target_weight: float,
        quantity_delta: float,
        fill_price: float,
        message: str,
        order_id: str | None = None,
        broker_order: dict[str, Any] | None = None,
        portfolio_history_points: int = 0,
    ) -> dict[str, Any]:
        qty = float(position.get("qty", 0) or 0)
        average_cost = float(position.get("avg_entry_price", 0) or 0)
        market_value = float(position.get("market_value", 0) or qty * fill_price)
        unrealized = float(position.get("unrealized_pl", 0) or 0)
        result = {
            "account_id": str(account.get("account_number") or account.get("id") or "alpaca-paper"),
            "status": status,
            "action": action,
            "ticker": state["ticker"].upper(),
            "target_weight": round(target_weight, 4),
            "quantity_delta": round(quantity_delta, 8),
            "fill_price": round(fill_price, 4),
            "fee": 0.0,
            "cash": round(float(account.get("cash", 0) or 0), 4),
            "equity": round(float(account.get("equity", account.get("portfolio_value", 0)) or 0), 4),
            "position_quantity": round(qty, 8),
            "average_cost": round(average_cost, 4),
            "market_value": round(market_value, 4),
            "unrealized_pnl": round(unrealized, 4),
            "realized_pnl": 0.0,
            "message": message,
            "provider": "alpaca",
            "portfolio_history_points": portfolio_history_points,
        }
        if order_id:
            result["order_id"] = order_id
        if broker_order:
            result["broker_order"] = broker_order
        return result

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            f"{self.base_url}{path}",
            data=body,
            method=method,
            headers={
                "APCA-API-KEY-ID": self.settings.api_key,
                "APCA-API-SECRET-KEY": self.settings.api_secret,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=20) as response:
                content = response.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Alpaca API HTTP {exc.code}: {detail[:500]}") from exc
        except URLError as exc:
            raise RuntimeError(f"Alpaca API request failed: {exc}") from exc
        if not content:
            return {}
        return json.loads(content)


def _target_weight(action: str, position_size: str) -> float:
    if action == "SELL":
        return 0.0
    if action == "HOLD":
        return TARGET_WEIGHTS.get(position_size, 0.0)
    return TARGET_WEIGHTS.get(position_size, 0.0)


def _quantity(delta_value: float, price: float, allow_fractional: bool) -> float:
    if price <= 0:
        return 0.0
    qty = delta_value / price
    if not allow_fractional:
        qty = float(int(qty))
    return round(qty, 8)


def _client_order_id(run_id: str, ticker: str) -> str:
    safe_run_id = "".join(char for char in run_id if char.isalnum() or char in {"-", "_"})
    return f"mmr-{ticker}-{safe_run_id}"[:48]


def _empty_result(state: dict[str, Any], status: str, message: str) -> dict[str, Any]:
    return {
        "account_id": "alpaca-paper",
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
        "provider": "alpaca",
    }


def _portfolio_order_result(order: dict[str, Any], status: str, message: str, *, provider: str) -> dict[str, Any]:
    return {
        "provider": provider,
        "status": status,
        "ticker": str(order.get("ticker", "")),
        "side": str(order.get("side", "")),
        "target_weight": float(order.get("target_weight", 0) or 0),
        "actual_weight": 0.0,
        "quantity_delta": 0.0,
        "fill_price": 0.0,
        "fee": 0.0,
        "message": message,
    }


def _alpaca_portfolio_order_result(
    *,
    order: dict[str, Any],
    broker_order: dict[str, Any],
    position: dict[str, Any],
    account: dict[str, Any],
    status: str,
    quantity_delta: float,
    fill_price: float,
    message: str,
) -> dict[str, Any]:
    qty = float(position.get("qty", 0) or 0)
    market_value = float(position.get("market_value", 0) or qty * fill_price)
    equity = float(account.get("equity", account.get("portfolio_value", 0)) or 0)
    return {
        "provider": "alpaca",
        "status": status,
        "ticker": str(order["ticker"]).upper(),
        "side": str(order.get("side", "")).upper(),
        "target_weight": round(float(order.get("target_weight", 0) or 0), 4),
        "actual_weight": round(market_value / equity, 6) if equity else 0.0,
        "quantity_delta": round(quantity_delta, 8),
        "fill_price": round(fill_price, 4),
        "fee": 0.0,
        "cash": round(float(account.get("cash", 0) or 0), 4),
        "equity": round(equity, 4),
        "position_quantity": round(qty, 8),
        "average_cost": round(float(position.get("avg_entry_price", 0) or 0), 4),
        "market_value": round(market_value, 4),
        "unrealized_pnl": round(float(position.get("unrealized_pl", 0) or 0), 4),
        "realized_pnl": 0.0,
        "estimated_delta_value": order.get("estimated_delta_value"),
        "order_id": str(broker_order.get("id", "")),
        "broker_order": broker_order,
        "message": message,
    }


def _portfolio_status(results: list[dict[str, Any]]) -> str:
    if not results:
        return "no_order"
    if any(result.get("status") in {"filled", "submitted", "accepted", "pending_new", "new"} for result in results):
        return "submitted"
    if any(result.get("status") == "rejected" for result in results):
        return "rejected"
    return str(results[0].get("status", "unknown"))
