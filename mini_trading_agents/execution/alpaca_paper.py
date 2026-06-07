from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from mini_trading_agents.execution.models import AlpacaPaperSettings, TARGET_WEIGHTS


class AlpacaPaperAdapter:
    """Alpaca paper trading adapter using the official REST API shape."""

    def __init__(self, settings: AlpacaPaperSettings) -> None:
        if not settings.api_key or not settings.api_secret:
            raise RuntimeError("Alpaca paper trading requires API key and secret.")
        self.settings = settings
        self.base_url = settings.base_url.rstrip("/")

    def apply_decision(self, run_id: str, state: dict[str, Any]) -> dict[str, Any]:
        decision = state.get("final_trade_decision")
        market = state.get("market_data")
        if not decision or not market:
            return _empty_result(state, "skipped", "Missing final decision or market data.")

        ticker = state["ticker"].upper()
        action = str(decision["action"]).upper()
        # The single-ticker graph treats position_size as conviction. The paper
        # broker adapter maps it to a target weight only for execution demos.
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

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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
