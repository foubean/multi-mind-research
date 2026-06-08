from __future__ import annotations

from typing import Any

from mini_trading_agents.llm_adapter import get_llm_adapter
from mini_trading_agents.portfolio_graph.nodes import demo_portfolio_manager


def portfolio_manager(state: dict[str, Any]) -> dict[str, Any]:
    if not state["llm_config"].get("enabled"):
        return demo_portfolio_manager(state)

    try:
        adapter = get_llm_adapter(state["llm_config"])
        result = adapter.response_wrapper(
            system_prompt=(
                "You are the global portfolio manager. Build a multi-ticker portfolio plan from "
                "single-ticker trade advice, account context, research summary, risk review, and "
                "hard constraints. Return only a feasible structured plan. Target weights are final "
                "portfolio-level allocations, unlike single-ticker position_size which is only conviction. "
                "Return target_weights as a list of ticker/weight objects, including CASH when useful. "
                "Explain why each selected ticker is bought or held, why rejected candidates are not used, "
                "why cash is retained, and how existing positions should be increased, reduced, or left unchanged."
            ),
            payload={
                "account_context": state["account_context"],
                "portfolio_constraints": state["portfolio_constraints"],
                "trade_advices": state.get("trade_advices", {}),
                "portfolio_research_summary": state.get("portfolio_research_summary", {}),
                "portfolio_risk_review": state.get("portfolio_risk_review", {}),
                "previous_validation_result": state.get("validation_result"),
                "revision_count": state.get("revision_count", 0),
            },
            schema_name="portfolio_plan",
            schema=_portfolio_plan_schema(),
        )
        result["target_weights"] = _normalize_target_weights(result["target_weights"])
        return {"portfolio_plan": result}
    except Exception as exc:
        raise RuntimeError(f"Global portfolio manager LLM failed: {type(exc).__name__}: {exc}") from exc


def revise_portfolio_plan(state: dict[str, Any]) -> dict[str, Any]:
    if not state["llm_config"].get("enabled"):
        from mini_trading_agents.portfolio_graph.nodes import revise_portfolio_plan as deterministic_revise

        return deterministic_revise(state)

    updated = dict(portfolio_manager(state)["portfolio_plan"])
    return {"portfolio_plan": updated, "revision_count": state.get("revision_count", 0) + 1}


def _portfolio_plan_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "decision",
            "target_weights",
            "orders",
            "rejected_candidates",
            "portfolio_rationale",
            "risk_controls",
        ],
        "properties": {
            "decision": {"type": "string", "enum": ["REBALANCE", "HOLD_CASH", "REDUCE_RISK"]},
            "target_weights": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["ticker", "weight"],
                    "properties": {
                        "ticker": {"type": "string"},
                        "weight": {"type": "number", "minimum": 0, "maximum": 1},
                    },
                },
            },
            "orders": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["ticker", "side", "target_weight", "priority", "reason"],
                    "properties": {
                        "ticker": {"type": "string"},
                        "side": {"type": "string", "enum": ["BUY", "SELL", "REDUCE", "HOLD"]},
                        "target_weight": {"type": "number", "minimum": 0, "maximum": 1},
                        "priority": {"type": "integer"},
                        "reason": {"type": "string"},
                    },
                },
            },
            "rejected_candidates": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["ticker", "reason"],
                    "properties": {"ticker": {"type": "string"}, "reason": {"type": "string"}},
                },
            },
            "portfolio_rationale": {"type": "string"},
            "risk_controls": {"type": "array", "items": {"type": "string"}},
        },
    }


def _normalize_target_weights(raw_weights: Any) -> dict[str, float]:
    if isinstance(raw_weights, dict):
        return {str(ticker).upper(): round(float(weight), 4) for ticker, weight in raw_weights.items()}
    if isinstance(raw_weights, list):
        return {
            str(item["ticker"]).upper(): round(float(item["weight"]), 4)
            for item in raw_weights
            if isinstance(item, dict) and item.get("ticker") is not None
        }
    raise RuntimeError("Portfolio manager returned target_weights in an unsupported format.")
