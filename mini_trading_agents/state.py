from __future__ import annotations

import operator
from typing import Annotated, Any, NotRequired, TypedDict


class Report(TypedDict):
    title: str
    signal: str
    confidence: float
    summary: str


class MarketData(TypedDict):
    ticker: str
    as_of: str
    source: str
    close: float
    change_pct: float
    volume: int
    average_volume_20d: float
    moving_average_20: float
    moving_average_60: float
    rsi_14: float
    macd: float
    volatility_20d: float
    observations: list[str]


class SentimentData(TypedDict):
    ticker: str
    as_of: str
    source: str
    sentiment_score: float
    positive_mentions: int
    negative_mentions: int
    neutral_mentions: int
    mention_change_pct_24h: float
    top_topics: list[str]
    observations: list[str]


class NewsItem(TypedDict):
    title: str
    source: str
    published_at: str
    summary: str
    url: str
    sentiment: str


class NewsData(TypedDict):
    ticker: str
    as_of: str
    source: str
    items: list[NewsItem]
    observations: list[str]


class FundamentalsData(TypedDict):
    ticker: str
    as_of: str
    source: str
    revenue_growth_yoy: float
    gross_margin: float
    operating_margin: float
    pe_ratio: float
    forward_pe: float
    debt_to_equity: float
    free_cash_flow: float
    cash_and_equivalents: float
    observations: list[str]


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
    data_providers: dict[str, str]
    # Parallel nodes may update trace in the same graph step, so this list needs
    # a reducer. operator.add appends all returned trace fragments.
    trace: Annotated[list[str], operator.add]

    data_status: NotRequired[dict[str, Any]]
    market_data: NotRequired[MarketData]
    sentiment_data: NotRequired[SentimentData]
    news_data: NotRequired[NewsData]
    fundamentals_data: NotRequired[FundamentalsData]

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
