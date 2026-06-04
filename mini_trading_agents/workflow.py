from __future__ import annotations

from mini_trading_agents import agents
from mini_trading_agents.graph import Workflow
from mini_trading_agents.state import TradingState


def initial_state(ticker: str, analysis_date: str) -> TradingState:
    return {
        "ticker": ticker.upper(),
        "analysis_date": analysis_date,
        "trace": [],
    }


def build_demo_workflow() -> Workflow:
    workflow = Workflow()

    workflow.add_node("market_analyst", agents.market_analyst)
    workflow.add_node("sentiment_analyst", agents.sentiment_analyst)
    workflow.add_node("news_analyst", agents.news_analyst)
    workflow.add_node("fundamentals_analyst", agents.fundamentals_analyst)

    workflow.add_node("bull_researcher", agents.bull_researcher)
    workflow.add_node("bear_researcher", agents.bear_researcher)
    workflow.add_node("research_manager", agents.research_manager)

    workflow.add_node("trader", agents.trader)

    workflow.add_node("aggressive_risk_debater", agents.aggressive_risk_debater)
    workflow.add_node("neutral_risk_debater", agents.neutral_risk_debater)
    workflow.add_node("conservative_risk_debater", agents.conservative_risk_debater)

    workflow.add_node("portfolio_manager", agents.portfolio_manager)
    return workflow
