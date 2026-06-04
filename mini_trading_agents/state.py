from __future__ import annotations

from typing import Any, NotRequired, TypedDict


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
    ticker: str
    analysis_date: str
    trace: list[str]

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
