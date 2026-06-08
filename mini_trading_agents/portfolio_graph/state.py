from __future__ import annotations

import operator
from typing import Annotated, Any, NotRequired, TypedDict


class AccountPosition(TypedDict):
    quantity: float
    market_value: float
    weight: float
    unrealized_pnl: float


class AccountContext(TypedDict):
    account_id: str
    cash: float
    equity: float
    base_currency: str
    positions: dict[str, AccountPosition]
    portfolio_history: list[dict[str, Any]]
    source: str


class PortfolioConstraints(TypedDict):
    long_only: bool
    allow_fractional: bool
    max_tickers: int
    max_single_position_pct: float
    max_total_equity_pct: float
    cash_reserve_pct: float
    max_turnover_pct: float
    max_sector_exposure_pct: float
    max_theme_exposure_pct: float
    max_correlation_cluster_pct: float
    max_new_positions: int
    min_order_value: float
    cooldown_days_after_loss: int
    no_trade_symbols: tuple[str, ...]


class TickerTask(TypedDict):
    ticker: str
    analysis_date: str
    data_providers: dict[str, str]
    trade_preferences: dict[str, Any]
    runtime_parameters: dict[str, Any]
    research_turns: int
    risk_turns: int


class TickerResult(TypedDict):
    ticker: str
    status: str
    final_state: NotRequired[dict[str, Any]]
    trade_advice: NotRequired[dict[str, Any]]
    final_trade_decision: NotRequired[dict[str, Any]]
    error: NotRequired[str]


class ValidationViolation(TypedDict):
    type: str
    severity: str
    message: str
    ticker: NotRequired[str]
    current: NotRequired[float]
    limit: NotRequired[float]


class ValidationResult(TypedDict):
    valid: bool
    status: str
    violations: list[ValidationViolation]
    warnings: list[str]


class PortfolioPlan(TypedDict):
    decision: str
    target_weights: dict[str, float]
    orders: list[dict[str, Any]]
    rejected_candidates: list[dict[str, Any]]
    portfolio_rationale: str
    risk_controls: list[str]


class GlobalPortfolioState(TypedDict):
    run_id: str
    analysis_date: str
    tickers: list[str]
    data_providers: dict[str, str]
    llm_config: dict[str, Any]
    runtime_parameters: dict[str, Any]
    trade_preferences: dict[str, Any]
    portfolio_config: dict[str, Any]
    portfolio_constraints: PortfolioConstraints
    account_context: NotRequired[AccountContext]
    preflight_result: NotRequired[ValidationResult]
    ticker_tasks: NotRequired[list[TickerTask]]
    ticker_task: NotRequired[TickerTask]
    ticker_results: Annotated[list[TickerResult], operator.add]
    trade_advices: NotRequired[dict[str, dict[str, Any]]]
    cross_section: NotRequired[dict[str, Any]]
    portfolio_context: NotRequired[dict[str, Any]]
    portfolio_research_summary: NotRequired[dict[str, Any]]
    portfolio_risk_review: NotRequired[dict[str, Any]]
    portfolio_plan: NotRequired[PortfolioPlan]
    validation_result: NotRequired[ValidationResult]
    revision_count: int
    max_revision_count: int
    execution_plan: NotRequired[dict[str, Any]]
    execution_validation_result: NotRequired[ValidationResult]
    rejected_plan: NotRequired[dict[str, Any]]
    report_path: NotRequired[str]
    trace: Annotated[list[str], operator.add]
