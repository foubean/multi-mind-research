from __future__ import annotations

from typing import Any


def preflight_validate(state: dict[str, Any]) -> dict[str, Any]:
    constraints = state["portfolio_constraints"]
    tickers = [str(ticker).upper() for ticker in state["tickers"]]
    violations: list[dict[str, Any]] = []
    warnings: list[str] = []

    if not tickers:
        violations.append(_fatal("empty_ticker_list", "At least one ticker is required."))
    if len(tickers) != len(set(tickers)):
        violations.append(_fatal("duplicate_ticker", "Ticker list contains duplicates."))
    if len(tickers) > int(constraints["max_tickers"]):
        violations.append(
            _fatal(
                "max_tickers",
                f"Ticker count {len(tickers)} exceeds max_tickers {constraints['max_tickers']}.",
                current=float(len(tickers)),
                limit=float(constraints["max_tickers"]),
            )
        )
    if float(constraints["max_single_position_pct"]) <= 0:
        violations.append(_fatal("max_single_position_pct", "max_single_position_pct must be positive."))
    if float(constraints["max_total_equity_pct"]) > 1:
        violations.append(_fatal("max_total_equity_pct", "max_total_equity_pct cannot exceed 1.0."))
    if float(constraints["cash_reserve_pct"]) < 0:
        violations.append(_fatal("cash_reserve_pct", "cash_reserve_pct cannot be negative."))
    if float(constraints["max_turnover_pct"]) < 0:
        violations.append(_fatal("max_turnover_pct", "max_turnover_pct cannot be negative."))
    no_trade = set(constraints.get("no_trade_symbols", ()))
    blocked = sorted(set(tickers).intersection(no_trade))
    if blocked:
        violations.append(_fatal("no_trade_symbols", f"Ticker list contains no-trade symbols: {', '.join(blocked)}."))
    providers = state.get("data_providers", {})
    for category in ["market", "sentiment", "news", "fundamentals"]:
        if category not in providers:
            violations.append(_fatal("missing_data_provider", f"Missing data provider for {category}."))
    if state["llm_config"].get("enabled") and not state["llm_config"].get("model"):
        violations.append(_fatal("missing_llm_model", "LLM is enabled but no model is configured."))

    if not state["llm_config"].get("enabled"):
        warnings.append("LLM is disabled; portfolio manager will use deterministic demo output.")

    status = "fatal" if violations else "valid"
    return {"valid": not violations, "status": status, "violations": violations, "warnings": warnings}


def validate_portfolio_plan(state: dict[str, Any]) -> dict[str, Any]:
    constraints = state["portfolio_constraints"]
    plan = state.get("portfolio_plan") or {}
    target_weights = {str(k).upper(): float(v) for k, v in (plan.get("target_weights") or {}).items()}
    violations: list[dict[str, Any]] = []
    warnings: list[str] = []
    checks: list[dict[str, Any]] = []

    total_weight = sum(weight for ticker, weight in target_weights.items() if ticker != "CASH")
    cash_weight = target_weights.get("CASH", max(0.0, 1.0 - total_weight))
    max_position = max((weight for ticker, weight in target_weights.items() if ticker != "CASH"), default=0.0)
    max_position_ticker = next(
        (ticker for ticker, weight in target_weights.items() if ticker != "CASH" and weight == max_position),
        "N/A",
    )

    checks.append(
        _check(
            "Total Equity Exposure",
            total_weight <= float(constraints["max_total_equity_pct"]) + 1e-6,
            current=round(total_weight, 6),
            limit=float(constraints["max_total_equity_pct"]),
        )
    )
    checks.append(
        _check(
            "Cash Reserve",
            cash_weight >= float(constraints["cash_reserve_pct"]) - 1e-6,
            current=round(cash_weight, 6),
            limit=float(constraints["cash_reserve_pct"]),
        )
    )
    checks.append(
        _check(
            f"Largest Single Position ({max_position_ticker})",
            max_position <= float(constraints["max_single_position_pct"]) + 1e-6,
            current=round(max_position, 6),
            limit=float(constraints["max_single_position_pct"]),
        )
    )
    checks.append(_check("Long Only", not constraints["long_only"] or all(weight >= -1e-6 for weight in target_weights.values())))
    current_positions = state.get("account_context", {}).get("positions", {})
    plan_turnover = sum(
        abs(weight - float(current_positions.get(ticker, {}).get("weight", 0.0)))
        for ticker, weight in target_weights.items()
        if ticker != "CASH"
    )
    checks.append(
        _check(
            "Plan Turnover",
            plan_turnover <= float(constraints["max_turnover_pct"]) + 1e-6,
            current=round(plan_turnover, 6),
            limit=float(constraints["max_turnover_pct"]),
        )
    )

    if total_weight > float(constraints["max_total_equity_pct"]) + 1e-6:
        violations.append(
            _repairable(
                "max_total_equity_pct",
                "Total equity weight exceeds portfolio limit.",
                current=round(total_weight, 6),
                limit=float(constraints["max_total_equity_pct"]),
            )
        )
    if cash_weight < float(constraints["cash_reserve_pct"]) - 1e-6:
        violations.append(
            _repairable(
                "cash_reserve_pct",
                "Cash reserve is below required minimum.",
                current=round(cash_weight, 6),
                limit=float(constraints["cash_reserve_pct"]),
            )
        )

    for ticker, weight in target_weights.items():
        if ticker == "CASH":
            continue
        if constraints["long_only"] and weight < -1e-6:
            violations.append(_fatal("long_only", "Short target weight is not allowed.", ticker=ticker, current=weight))
        if weight > float(constraints["max_single_position_pct"]) + 1e-6:
            violations.append(
                _repairable(
                    "max_single_position_pct",
                    "Single ticker target weight exceeds limit.",
                    ticker=ticker,
                    current=round(weight, 6),
                    limit=float(constraints["max_single_position_pct"]),
                )
            )
        if ticker in set(constraints.get("no_trade_symbols", ())):
            violations.append(_fatal("no_trade_symbols", "Target plan includes a no-trade symbol.", ticker=ticker))

    existing_positions = set(state.get("account_context", {}).get("positions", {}))
    new_positions = [ticker for ticker, weight in target_weights.items() if ticker != "CASH" and weight > 0 and ticker not in existing_positions]
    checks.append(
        _check(
            "New Position Count",
            len(new_positions) <= int(constraints["max_new_positions"]),
            current=float(len(new_positions)),
            limit=float(constraints["max_new_positions"]),
        )
    )
    if len(new_positions) > int(constraints["max_new_positions"]):
        violations.append(
            _repairable(
                "max_new_positions",
                "New position count exceeds configured limit.",
                current=float(len(new_positions)),
                limit=float(constraints["max_new_positions"]),
            )
        )
    if plan_turnover > float(constraints["max_turnover_pct"]) + 1e-6:
        violations.append(
            _repairable(
                "max_turnover_pct",
                "Portfolio plan turnover exceeds configured limit.",
                current=round(plan_turnover, 6),
                limit=float(constraints["max_turnover_pct"]),
            )
        )

    status = "valid"
    if any(item["severity"] == "fatal" for item in violations):
        status = "fatal"
    elif violations:
        status = "repairable"
    return {"valid": not violations, "status": status, "violations": violations, "warnings": warnings, "checks": checks}


def validate_execution_plan(state: dict[str, Any]) -> dict[str, Any]:
    constraints = state["portfolio_constraints"]
    execution = state.get("execution_plan") or {}
    orders = execution.get("orders", [])
    violations: list[dict[str, Any]] = []
    warnings: list[str] = []
    checks: list[dict[str, Any]] = []
    equity = float(state.get("account_context", {}).get("equity", execution.get("equity", 0)) or 0)
    turnover = 0.0
    min_order_value = float(constraints["min_order_value"])

    for order in orders:
        delta_value = abs(float(order.get("estimated_delta_value", order.get("estimated_value", 0))))
        turnover += delta_value
        if 0 < delta_value < min_order_value:
            violations.append(
                _repairable(
                    "min_order_value",
                    "Order delta is below minimum order value.",
                    ticker=str(order.get("ticker", "")),
                    current=round(delta_value, 2),
                    limit=min_order_value,
                )
            )
    turnover_pct = turnover / equity if equity else 0.0
    checks.append(
        _check(
            "Execution Turnover",
            turnover_pct <= float(constraints["max_turnover_pct"]) + 1e-6,
            current=round(turnover_pct, 6),
            limit=float(constraints["max_turnover_pct"]),
        )
    )
    checks.append(
        _check(
            "Minimum Order Value",
            not any(item["type"] == "min_order_value" for item in violations),
            current=min_order_value,
            limit=min_order_value,
        )
    )
    if turnover_pct > float(constraints["max_turnover_pct"]) + 1e-6:
        violations.append(
            _repairable(
                "max_turnover_pct",
                "Execution turnover exceeds configured limit.",
                current=round(turnover_pct, 6),
                limit=float(constraints["max_turnover_pct"]),
            )
        )

    status = "valid"
    if any(item["severity"] == "fatal" for item in violations):
        status = "fatal"
    elif violations:
        status = "repairable"
    return {"valid": not violations, "status": status, "violations": violations, "warnings": warnings, "checks": checks}


def _fatal(kind: str, message: str, **extra: Any) -> dict[str, Any]:
    return {"type": kind, "severity": "fatal", "message": message, **extra}


def _repairable(kind: str, message: str, **extra: Any) -> dict[str, Any]:
    return {"type": kind, "severity": "repairable", "message": message, **extra}


def _check(name: str, passed: bool, **extra: Any) -> dict[str, Any]:
    return {"name": name, "passed": passed, **extra}
