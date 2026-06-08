from __future__ import annotations

from typing import Any, Literal

from langgraph.constants import END, START
from langgraph.graph import StateGraph
from langgraph.types import Send

from mini_trading_agents.portfolio_graph import llm_agents, nodes
from mini_trading_agents.portfolio_graph.state import GlobalPortfolioState


def build_portfolio_workflow(*, checkpointer=None, store=None):
    graph = StateGraph(GlobalPortfolioState)
    graph.add_node("load_account_context", _with_trace("load_account_context", nodes.load_account_context))
    graph.add_node("preflight_validate", _with_trace("preflight_validate", nodes.preflight_validate_node))
    graph.add_node("prepare_ticker_tasks", _with_trace("prepare_ticker_tasks", nodes.prepare_ticker_tasks))
    graph.add_node("dispatch_ticker_batch", _with_trace("dispatch_ticker_batch", nodes.dispatch_ticker_batch))
    graph.add_node("run_single_ticker_node", _with_trace("run_single_ticker_node", nodes.run_single_ticker_node))
    graph.add_node("collect_trade_advices", _with_trace("collect_trade_advices", nodes.collect_trade_advices))
    graph.add_node("build_portfolio_context", _with_trace("build_portfolio_context", nodes.build_portfolio_context))
    graph.add_node(
        "portfolio_research_summarizer",
        _with_trace("portfolio_research_summarizer", nodes.portfolio_research_summarizer),
    )
    graph.add_node("portfolio_risk_reviewer", _with_trace("portfolio_risk_reviewer", nodes.portfolio_risk_reviewer))
    graph.add_node("portfolio_manager", _with_trace("portfolio_manager", llm_agents.portfolio_manager))
    graph.add_node("validate_portfolio_plan", _with_trace("validate_portfolio_plan", nodes.validate_portfolio_plan_node))
    graph.add_node("revise_portfolio_plan", _with_trace("revise_portfolio_plan", llm_agents.revise_portfolio_plan))
    graph.add_node("rejected_portfolio_plan", _with_trace("rejected_portfolio_plan", nodes.rejected_portfolio_plan))
    graph.add_node("execution_planner", _with_trace("execution_planner", nodes.execution_planner))
    graph.add_node("validate_execution_plan", _with_trace("validate_execution_plan", nodes.validate_execution_plan_node))

    graph.add_edge(START, "load_account_context")
    graph.add_edge("load_account_context", "preflight_validate")
    graph.add_conditional_edges(
        "preflight_validate",
        _route_preflight,
        {"continue": "prepare_ticker_tasks", "reject": "rejected_portfolio_plan"},
    )
    graph.add_edge("prepare_ticker_tasks", "dispatch_ticker_batch")
    graph.add_conditional_edges(
        "dispatch_ticker_batch",
        _route_ticker_dispatch,
        ["run_single_ticker_node", "collect_trade_advices"],
    )
    graph.add_edge("run_single_ticker_node", "dispatch_ticker_batch")
    graph.add_edge("collect_trade_advices", "build_portfolio_context")
    graph.add_edge("build_portfolio_context", "portfolio_research_summarizer")
    graph.add_edge("portfolio_research_summarizer", "portfolio_risk_reviewer")
    graph.add_edge("portfolio_risk_reviewer", "portfolio_manager")
    graph.add_edge("portfolio_manager", "validate_portfolio_plan")
    graph.add_conditional_edges(
        "validate_portfolio_plan",
        _route_validation,
        {
            "execute": "execution_planner",
            "revise": "revise_portfolio_plan",
            "reject": "rejected_portfolio_plan",
        },
    )
    graph.add_edge("revise_portfolio_plan", "validate_portfolio_plan")
    graph.add_edge("execution_planner", "validate_execution_plan")
    graph.add_conditional_edges(
        "validate_execution_plan",
        _route_execution_validation,
        {"finish": END, "reject": "rejected_portfolio_plan"},
    )
    graph.add_edge("rejected_portfolio_plan", END)
    return graph.compile(checkpointer=checkpointer, store=store)


def initial_portfolio_state(
    *,
    run_id: str,
    tickers: list[str],
    analysis_date: str,
    data_providers: dict[str, str],
    data_provider_config: dict[str, Any],
    app_config: Any,
) -> GlobalPortfolioState:
    return {
        "run_id": run_id,
        "analysis_date": analysis_date,
        "tickers": [ticker.upper() for ticker in tickers],
        "data_providers": data_providers,
        "data_provider_config": data_provider_config,
        "llm_config": app_config.llm.__dict__,
        "trade_preferences": app_config.trade_preferences.__dict__,
        "portfolio_config": {
            "max_revision_count": app_config.portfolio.max_revision_count,
            "single_ticker_failure_policy": app_config.portfolio.single_ticker_failure_policy,
            "research_turns": app_config.run.research_turns,
            "risk_turns": app_config.run.risk_turns,
            "max_parallel_tickers": app_config.run.max_parallel_tickers,
            "paper_trading": app_config.paper_trading.__dict__,
            "storage_path": app_config.persistence.storage_path,
        },
        "portfolio_constraints": app_config.portfolio.constraints.__dict__,
        "ticker_results": [],
        "revision_count": 0,
        "max_revision_count": app_config.portfolio.max_revision_count,
        "trace": [],
    }


def _route_preflight(state: GlobalPortfolioState) -> Literal["continue", "reject"]:
    return "continue" if state.get("preflight_result", {}).get("valid") else "reject"


def _fanout_ticker_tasks(state: GlobalPortfolioState) -> list[Send]:
    shared = {
        "llm_config": state["llm_config"],
        "data_provider_config": state.get("data_provider_config", {}),
        "portfolio_config": state["portfolio_config"],
        "ticker_results": [],
        "trace": [],
    }
    return [Send("run_single_ticker_node", {**shared, "ticker_task": task}) for task in state.get("active_ticker_tasks", [])]


def _route_ticker_dispatch(state: GlobalPortfolioState):
    if state.get("active_ticker_tasks"):
        return _fanout_ticker_tasks(state)
    return "collect_trade_advices"


def _route_validation(state: GlobalPortfolioState) -> Literal["execute", "revise", "reject"]:
    result = state.get("validation_result", {})
    if result.get("valid"):
        return "execute"
    if result.get("status") == "repairable" and state.get("revision_count", 0) < state.get("max_revision_count", 2):
        return "revise"
    return "reject"


def _route_execution_validation(state: GlobalPortfolioState) -> Literal["finish", "reject"]:
    result = state.get("execution_validation_result", {})
    return "finish" if result.get("valid") else "reject"


def _with_trace(name: str, node):
    def wrapped(state: GlobalPortfolioState) -> dict:
        updates = dict(node(state))
        updates["trace"] = [name]
        return updates

    return wrapped
