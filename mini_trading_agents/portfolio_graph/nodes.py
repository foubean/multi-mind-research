from __future__ import annotations

import json
import os
from typing import Any

from mini_trading_agents.execution.alpaca_paper import AlpacaPaperAdapter
from mini_trading_agents.execution.models import AlpacaPaperSettings
from mini_trading_agents.workflow import build_demo_workflow, initial_state
from mini_trading_agents.portfolio_graph.constraints import (
    preflight_validate,
    validate_execution_plan,
    validate_portfolio_plan,
)


def load_account_context(state: dict[str, Any]) -> dict[str, Any]:
    paper = state["portfolio_config"].get("paper_trading", {})
    provider = str(paper.get("provider", "alpaca")).lower()
    if provider != "alpaca":
        raise RuntimeError(f"Unsupported online paper trading provider: {provider}")
    adapter = AlpacaPaperAdapter(
        AlpacaPaperSettings(
            api_key=os.getenv("ALPACA_API_KEY", ""),
            api_secret=os.getenv("ALPACA_API_SECRET", ""),
            base_url=str(paper.get("alpaca_base_url", "https://paper-api.alpaca.markets")),
            allow_fractional=bool(paper.get("allow_fractional", True)),
        )
    )
    return {"account_context": adapter.get_account_context()}


def preflight_validate_node(state: dict[str, Any]) -> dict[str, Any]:
    return {"preflight_result": preflight_validate(state)}


def prepare_ticker_tasks(state: dict[str, Any]) -> dict[str, Any]:
    config = state["portfolio_config"]
    tasks = [
        {
            "ticker": ticker,
            "analysis_date": state["analysis_date"],
            "data_providers": state["data_providers"],
            "trade_preferences": state["trade_preferences"],
            "research_turns": int(config.get("research_turns", 2)),
            "risk_turns": int(config.get("risk_turns", 3)),
        }
        for ticker in state["tickers"]
    ]
    return {"ticker_tasks": tasks, "ticker_task_queue": tasks, "active_ticker_tasks": [], "dispatch_round": 0}


def dispatch_ticker_batch(state: dict[str, Any]) -> dict[str, Any]:
    queue = list(state.get("ticker_task_queue", []))
    max_parallel = max(1, int(state["portfolio_config"].get("max_parallel_tickers", 5)))
    batch = queue[:max_parallel]
    remaining = queue[max_parallel:]
    return {
        "active_ticker_tasks": batch,
        "ticker_task_queue": remaining,
        "dispatch_round": int(state.get("dispatch_round", 0)) + 1,
    }


def run_single_ticker_node(state: dict[str, Any]) -> dict[str, Any]:
    task = state["ticker_task"]
    ticker = task["ticker"]
    try:
        ticker_state = initial_state(
            ticker,
            task["analysis_date"],
            max_research_debate_turns=int(task["research_turns"]),
            max_risk_debate_turns=int(task["risk_turns"]),
            data_providers=task["data_providers"],
            data_provider_config=state.get("data_provider_config", {}),
            trade_preferences=task["trade_preferences"],
            llm_config=state["llm_config"],
        )
        final_state = build_demo_workflow().invoke(ticker_state)
        result = {
            "ticker": ticker,
            "status": "ok",
            "final_state": final_state,
            "trade_advice": final_state.get("trade_advice"),
            "final_trade_decision": final_state.get("final_trade_decision"),
        }
    except Exception as exc:
        if state["portfolio_config"].get("single_ticker_failure_policy", "fail_fast") == "fail_fast":
            raise
        result = {"ticker": ticker, "status": "error", "error": str(exc)}
    return {"ticker_results": [result]}


def collect_trade_advices(state: dict[str, Any]) -> dict[str, Any]:
    advices = {
        result["ticker"]: result["trade_advice"]
        for result in state.get("ticker_results", [])
        if result.get("status") == "ok" and result.get("trade_advice")
    }
    return {"trade_advices": advices, "cross_section": _build_cross_section(advices, state.get("ticker_results", []))}


def build_portfolio_context(state: dict[str, Any]) -> dict[str, Any]:
    advices = state.get("trade_advices", {})
    cross_section = state.get("cross_section") or _build_cross_section(advices, state.get("ticker_results", []))
    return {
        "portfolio_context": {
            "account": state["account_context"],
            "constraints": state["portfolio_constraints"],
            "ticker_advices": advices,
            "cross_section": cross_section,
            "recent_memory": state.get("recent_memory", []),
            "current_positions": state["account_context"].get("positions", {}),
        }
    }


def portfolio_research_summarizer(state: dict[str, Any]) -> dict[str, Any]:
    advices = state.get("trade_advices", {})
    cross_section = state["portfolio_context"]["cross_section"]
    ranked = cross_section["ranked_candidates"]
    conflicts = [
        f"{ticker} has BUY action but trade intent is {advices[ticker].get('trade_intent')}"
        for ticker in cross_section.get("buy_candidates", [])
        if advices[ticker].get("trade_intent") in {"wait", "watch"}
    ]
    return {
        "portfolio_research_summary": {
            "opportunity_ranking": ranked,
            "summary": f"Reviewed {len(advices)} ticker advices. Top candidates: {', '.join(ranked[:3]) or 'none'}.",
            "conflicts": conflicts,
            "theme_clusters": _theme_clusters(advices),
            "action_distribution": cross_section.get("action_distribution", {}),
        }
    }


def portfolio_risk_reviewer(state: dict[str, Any]) -> dict[str, Any]:
    advices = state.get("trade_advices", {})
    positions = state["account_context"].get("positions", {})
    constraints = state["portfolio_constraints"]
    elevated = [
        ticker
        for ticker, advice in advices.items()
        if float(advice.get("expected_risk_pct", 0)) >= float(constraints["max_single_position_pct"]) / 2
    ]
    existing_overlap = sorted(set(positions).intersection(advices))
    buy_count = len([advice for advice in advices.values() if advice.get("action") == "BUY"])
    return {
        "portfolio_risk_review": {
            "risk_flags": elevated,
            "concentration_notes": [
                f"{buy_count} BUY candidates will be capped by max_new_positions={constraints['max_new_positions']}.",
                f"Existing position overlap: {', '.join(existing_overlap) or 'none'}.",
            ],
            "cash_notes": f"Required cash reserve: {constraints['cash_reserve_pct']:.1%}.",
            "position_overlap": existing_overlap,
            "risk_summary": (
                "Portfolio risk review checks candidate count, existing holdings, cash reserve, "
                "single-position caps, and elevated expected-risk tickers before LLM allocation."
            ),
        }
    }


def demo_portfolio_manager(state: dict[str, Any]) -> dict[str, Any]:
    advices = state.get("trade_advices", {})
    constraints = state["portfolio_constraints"]
    buy_advices = {
        ticker: advice for ticker, advice in advices.items() if advice.get("action") == "BUY"
    }
    if not buy_advices:
        return {"portfolio_plan": _cash_plan("No BUY candidates after single-ticker analysis.")}

    max_single = float(constraints["max_single_position_pct"])
    max_total = float(constraints["max_total_equity_pct"])
    cash_reserve = float(constraints["cash_reserve_pct"])
    total_budget = min(max_total, 1.0 - cash_reserve, float(constraints.get("max_turnover_pct", max_total)))
    raw_scores = {
        ticker: max(
            0.0,
            float(advice.get("confidence", 0))
            * max(0.01, float(advice.get("expected_return_pct", 0)))
            / max(0.01, float(advice.get("expected_risk_pct", 0.01))),
        )
        for ticker, advice in buy_advices.items()
    }
    score_sum = sum(raw_scores.values()) or 1.0
    target_weights: dict[str, float] = {}
    for ticker, score in raw_scores.items():
        target_weights[ticker] = round(min(max_single, total_budget * score / score_sum), 4)
    target_weights = _fit_weight_budget(target_weights, total_budget)
    used = sum(target_weights.values())
    target_weights["CASH"] = round(max(0.0, 1.0 - used), 4)
    return {"portfolio_plan": _plan_from_weights(target_weights, advices, "Demo portfolio plan from deterministic weighting.")}


def validate_portfolio_plan_node(state: dict[str, Any]) -> dict[str, Any]:
    return {"validation_result": validate_portfolio_plan(state)}


def revise_portfolio_plan(state: dict[str, Any]) -> dict[str, Any]:
    plan = dict(state["portfolio_plan"])
    constraints = state["portfolio_constraints"]
    weights = {ticker: float(weight) for ticker, weight in plan.get("target_weights", {}).items()}
    max_single = float(constraints["max_single_position_pct"])
    max_total = float(constraints["max_total_equity_pct"])
    cash_reserve = float(constraints["cash_reserve_pct"])

    for ticker in list(weights):
        if ticker != "CASH":
            weights[ticker] = max(0.0, min(weights[ticker], max_single))
    total = sum(weight for ticker, weight in weights.items() if ticker != "CASH")
    budget = min(max_total, 1.0 - cash_reserve)
    if total > budget and total > 0:
        scale = budget / total
        for ticker in list(weights):
            if ticker != "CASH":
                weights[ticker] = round(weights[ticker] * scale, 4)
    used = sum(weight for ticker, weight in weights.items() if ticker != "CASH")
    if used > budget:
        weights = _fit_weight_budget({ticker: weight for ticker, weight in weights.items() if ticker != "CASH"}, budget)
        used = sum(weights.values())
    weights["CASH"] = round(max(cash_reserve, 1.0 - used), 4)
    plan["target_weights"] = weights
    plan["portfolio_rationale"] = plan.get("portfolio_rationale", "") + " Revised to satisfy hard constraints."
    return {"portfolio_plan": plan, "revision_count": state.get("revision_count", 0) + 1}


def rejected_portfolio_plan(state: dict[str, Any]) -> dict[str, Any]:
    result = state.get("execution_validation_result") or state.get("validation_result") or state.get("preflight_result") or {}
    return {
        "rejected_plan": {
            "status": "rejected",
            "reason": "Portfolio plan failed validation.",
            "violations": result.get("violations", []),
            "partial_results": state.get("trade_advices", {}),
        }
    }


def execution_planner(state: dict[str, Any]) -> dict[str, Any]:
    plan = state["portfolio_plan"]
    equity = float(state["account_context"]["equity"])
    current_positions = state["account_context"].get("positions", {})
    orders = []
    for ticker, weight in plan["target_weights"].items():
        if ticker == "CASH" or weight <= 0:
            continue
        current_weight = float(current_positions.get(ticker, {}).get("weight", 0.0))
        delta_weight = weight - current_weight
        orders.append(
            {
                "ticker": ticker,
                "side": "BUY",
                "target_weight": weight,
                "current_weight": round(current_weight, 4),
                "delta_weight": round(delta_weight, 4),
                "estimated_value": round(equity * weight, 2),
                "estimated_delta_value": round(equity * delta_weight, 2),
                "order_type": "market",
                "time_in_force": "day",
                "reason": _order_reason(plan, ticker),
            }
        )
    return {"execution_plan": {"status": "planned", "orders": orders, "equity": equity}}


def validate_execution_plan_node(state: dict[str, Any]) -> dict[str, Any]:
    return {"execution_validation_result": validate_execution_plan(state)}


def _cash_plan(reason: str) -> dict[str, Any]:
    return {
        "decision": "HOLD_CASH",
        "target_weights": {"CASH": 1.0},
        "orders": [],
        "rejected_candidates": [],
        "portfolio_rationale": reason,
        "risk_controls": ["Keep full cash allocation until actionable candidates appear."],
    }


def _plan_from_weights(target_weights: dict[str, float], advices: dict[str, Any], rationale: str) -> dict[str, Any]:
    orders = [
        {
            "ticker": ticker,
            "side": "BUY",
            "target_weight": weight,
            "priority": index + 1,
            "reason": advices.get(ticker, {}).get("rationale", "Selected by portfolio manager."),
        }
        for index, (ticker, weight) in enumerate(target_weights.items())
        if ticker != "CASH" and weight > 0
    ]
    return {
        "decision": "REBALANCE" if orders else "HOLD_CASH",
        "target_weights": target_weights,
        "orders": orders,
        "rejected_candidates": [
            {"ticker": ticker, "reason": "Not selected for portfolio allocation."}
            for ticker, advice in advices.items()
            if ticker not in target_weights and advice.get("action") != "SELL"
        ],
        "portfolio_rationale": rationale,
        "risk_controls": ["Respect configured cash reserve, total equity cap, and single-position cap."],
    }


def _order_reason(plan: dict[str, Any], ticker: str) -> str:
    for order in plan.get("orders", []):
        if order.get("ticker") == ticker:
            return str(order.get("reason", "Portfolio rebalance order."))
    return "Portfolio rebalance order."


def _fit_weight_budget(weights: dict[str, float], budget: float) -> dict[str, float]:
    total = sum(weights.values())
    if total <= budget or total <= 0:
        return weights
    scale = budget / total
    fitted = {ticker: round(weight * scale, 4) for ticker, weight in weights.items()}
    overflow = round(sum(fitted.values()) - budget, 6)
    if overflow > 0 and fitted:
        largest = max(fitted, key=fitted.get)
        fitted[largest] = round(max(0.0, fitted[largest] - overflow), 4)
    return fitted


def _build_cross_section(advices: dict[str, dict[str, Any]], results: list[dict[str, Any]]) -> dict[str, Any]:
    action_distribution = {action: 0 for action in ["BUY", "HOLD", "SELL"]}
    intent_distribution: dict[str, int] = {}
    for advice in advices.values():
        action_distribution[str(advice.get("action", "HOLD"))] = action_distribution.get(str(advice.get("action")), 0) + 1
        intent = str(advice.get("trade_intent", "unknown"))
        intent_distribution[intent] = intent_distribution.get(intent, 0) + 1

    ranked = sorted(
        advices.items(),
        key=lambda item: (
            float(item[1].get("confidence", 0)),
            float(item[1].get("expected_return_pct", 0)) - float(item[1].get("expected_risk_pct", 0)),
        ),
        reverse=True,
    )
    return {
        "action_distribution": action_distribution,
        "intent_distribution": intent_distribution,
        "buy_candidates": [ticker for ticker, advice in advices.items() if advice.get("action") == "BUY"],
        "hold_candidates": [ticker for ticker, advice in advices.items() if advice.get("action") == "HOLD"],
        "sell_candidates": [ticker for ticker, advice in advices.items() if advice.get("action") == "SELL"],
        "ranked_candidates": [ticker for ticker, _ in ranked],
        "confidence_ranking": [
            {"ticker": ticker, "confidence": advice.get("confidence", 0)}
            for ticker, advice in sorted(advices.items(), key=lambda item: float(item[1].get("confidence", 0)), reverse=True)
        ],
        "risk_return_ranking": [
            {
                "ticker": ticker,
                "score": round(float(advice.get("expected_return_pct", 0)) - float(advice.get("expected_risk_pct", 0)), 4),
            }
            for ticker, advice in ranked
        ],
        "failed_tickers": [
            {"ticker": result.get("ticker"), "error": result.get("error")}
            for result in results
            if result.get("status") == "error"
        ],
    }


def _theme_clusters(advices: dict[str, Any]) -> list[dict[str, Any]]:
    clusters: dict[str, list[str]] = {}
    for ticker, advice in advices.items():
        rationale = json.dumps(advice, ensure_ascii=False).lower()
        if "ai" in rationale:
            clusters.setdefault("AI", []).append(ticker)
        if "valuation" in rationale:
            clusters.setdefault("Valuation Risk", []).append(ticker)
        if "momentum" in rationale:
            clusters.setdefault("Momentum", []).append(ticker)
    return [{"theme": theme, "tickers": tickers} for theme, tickers in clusters.items()]
