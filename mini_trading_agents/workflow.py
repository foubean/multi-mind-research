from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from langgraph.graph import END, START, StateGraph

from mini_trading_agents import agents
from mini_trading_agents.data_layer import prepare_data
from mini_trading_agents.state import TradingState


ANALYST_NODES = [
    "market_analyst",
    "sentiment_analyst",
    "news_analyst",
    "fundamentals_analyst",
]


Node = Callable[[TradingState], dict]


def build_demo_workflow(checkpointer=None, store=None):
    graph = StateGraph(TradingState)

    graph.add_node("prepare_data", _with_trace("prepare_data", prepare_data))

    graph.add_node("market_analyst", _with_trace("market_analyst", agents.market_analyst))
    graph.add_node("sentiment_analyst", _with_trace("sentiment_analyst", agents.sentiment_analyst))
    graph.add_node("news_analyst", _with_trace("news_analyst", agents.news_analyst))
    graph.add_node("fundamentals_analyst", _with_trace("fundamentals_analyst", agents.fundamentals_analyst))

    graph.add_node("bull_researcher", _with_trace("bull_researcher", agents.bull_researcher))
    graph.add_node("bear_researcher", _with_trace("bear_researcher", agents.bear_researcher))
    graph.add_node("research_manager", _with_trace("research_manager", agents.research_manager))

    graph.add_node("trader", _with_trace("trader", agents.trader))

    graph.add_node("aggressive_risk_debater", _with_trace("aggressive_risk_debater", agents.aggressive_risk_debater))
    graph.add_node("neutral_risk_debater", _with_trace("neutral_risk_debater", agents.neutral_risk_debater))
    graph.add_node("conservative_risk_debater", _with_trace("conservative_risk_debater", agents.conservative_risk_debater))

    graph.add_node("portfolio_manager", _with_trace("portfolio_manager", agents.portfolio_manager))

    # prepare_data is the data layer boundary: it fetches, cleans, and
    # structures raw provider data before analysts read their own state fields.
    graph.add_edge(START, "prepare_data")

    # One edge from prepare_data to each analyst means the analyst stage fans out:
    # LangGraph can run these independent nodes in parallel against the same
    # input state instead of chaining them one by one.
    for node_name in ANALYST_NODES:
        graph.add_edge("prepare_data", node_name)

    # A list of source nodes creates a join: bull_researcher waits until all
    # analyst nodes have produced their partial state updates.
    graph.add_edge(ANALYST_NODES, "bull_researcher")
    graph.add_edge("bull_researcher", "bear_researcher")

    # Conditional edges make the bull/bear debate a loop. After each bear turn,
    # _route_research_debate checks the shared debate counter and chooses either
    # to send control back to bull_researcher or forward to research_manager.
    graph.add_conditional_edges(
        "bear_researcher",
        _route_research_debate,
        {
            "continue_research_debate": "bull_researcher",
            "finish_research_debate": "research_manager",
        },
    )

    graph.add_edge("research_manager", "trader")
    graph.add_edge("trader", "aggressive_risk_debater")
    graph.add_edge("aggressive_risk_debater", "neutral_risk_debater")
    graph.add_edge("neutral_risk_debater", "conservative_risk_debater")

    # Risk debate uses the same pattern as research debate: conservative is the
    # last speaker in a round, so it decides whether the risk loop continues or
    # the portfolio manager can make the final decision.
    graph.add_conditional_edges(
        "conservative_risk_debater",
        _route_risk_debate,
        {
            "continue_risk_debate": "aggressive_risk_debater",
            "finish_risk_debate": "portfolio_manager",
        },
    )
    graph.add_edge("portfolio_manager", END)

    return graph.compile(checkpointer=checkpointer, store=store)


def initial_state(
    ticker: str,
    analysis_date: str,
    max_research_debate_turns: int = 4,
    max_risk_debate_turns: int = 6,
    data_providers: dict[str, str] | None = None,
    data_provider_config: dict | None = None,
    trade_preferences: dict | None = None,
    llm_config: dict | None = None,
) -> TradingState:
    providers = data_providers or {
        "market": "sample",
        "sentiment": "sample",
        "news": "sample",
        "fundamentals": "sample",
    }
    return {
        "ticker": ticker.upper(),
        "analysis_date": analysis_date,
        "max_research_debate_turns": max_research_debate_turns,
        "max_risk_debate_turns": max_risk_debate_turns,
        "data_providers": providers,
        "data_provider_config": data_provider_config or {},
        "trade_preferences": trade_preferences
        or {
            "risk_profile": "balanced",
            "trading_style": "staged",
            "target_return_pct": 0.12,
            "max_drawdown_pct": 0.08,
            "expected_holding_days": 20,
        },
        "llm_config": llm_config or {"enabled": False},
        "trace": [],
    }


def _with_trace(name: str, node: Node) -> Node:
    def wrapped(state: TradingState) -> dict:
        updates = dict(node(state))
        # trace has an operator.add reducer in TradingState, so returning a
        # one-item list appends safely even when several parallel nodes finish
        # during the same graph step.
        updates["trace"] = [name]
        return updates

    return wrapped


def _route_research_debate(
    state: TradingState,
) -> Literal["continue_research_debate", "finish_research_debate"]:
    debate_count = state["investment_debate_state"]["count"]
    if debate_count < state["max_research_debate_turns"]:
        return "continue_research_debate"
    return "finish_research_debate"


def _route_risk_debate(
    state: TradingState,
) -> Literal["continue_risk_debate", "finish_risk_debate"]:
    debate_count = state["risk_debate_state"]["count"]
    if debate_count < state["max_risk_debate_turns"]:
        return "continue_risk_debate"
    return "finish_risk_debate"
