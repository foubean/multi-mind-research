from __future__ import annotations

import operator
from typing import Annotated, Any, NotRequired, TypedDict


class Report(TypedDict):
    title: str
    signal: str
    confidence: float
    summary: str


class DebateState(TypedDict):
    history: list[str]
    latest_speaker: str
    count: int


class TradeProposal(TypedDict):
    action: str
    position_size: str
    confidence: float
    rationale: str


class FinalDecision(TypedDict):
    action: str
    position_size: str
    confidence: float
    reason: str


class TradingState(TypedDict):
    # TradingState is the shared blackboard for all graph nodes. Nodes read the
    # current state and return partial updates; LangGraph merges those updates
    # into the next state.
    ticker: str
    analysis_date: str
    max_research_debate_turns: int
    max_risk_debate_turns: int
    # Parallel nodes may update trace in the same graph step, so this list needs
    # a reducer. operator.add appends all returned trace fragments.
    trace: Annotated[list[str], operator.add]

    market_report: NotRequired[Report]
    sentiment_report: NotRequired[Report]
    news_report: NotRequired[Report]
    fundamentals_report: NotRequired[Report]

    investment_debate_state: NotRequired[DebateState]
    investment_plan: NotRequired[dict[str, Any]]
    trader_investment_plan: NotRequired[TradeProposal]

    risk_debate_state: NotRequired[DebateState]
    risk_assessment: NotRequired[dict[str, Any]]
    final_trade_decision: NotRequired[FinalDecision]
