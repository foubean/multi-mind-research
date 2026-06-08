from __future__ import annotations

from dataclasses import dataclass


TARGET_WEIGHTS = {
    "none": 0.0,
    "small": 0.10,
    "medium": 0.25,
    "large": 0.50,
}


@dataclass(frozen=True)
class PaperTradingSettings:
    account_id: str
    initial_cash: float
    base_currency: str
    fee_rate: float
    slippage_bps: float
    allow_fractional: bool


@dataclass(frozen=True)
class AlpacaPaperSettings:
    api_key: str
    api_secret: str
    base_url: str
    allow_fractional: bool


@dataclass(frozen=True)
class AccountSnapshot:
    account_id: str
    cash: float
    equity: float
    base_currency: str


@dataclass(frozen=True)
class PositionSnapshot:
    ticker: str
    quantity: float
    average_cost: float
    last_price: float
    market_value: float
    unrealized_pnl: float
    realized_pnl: float


def latest_prices_from_portfolio_state(state: dict) -> dict[str, float]:
    prices: dict[str, float] = {}
    for result in state.get("ticker_results", []):
        ticker = str(result.get("ticker", "")).upper()
        final_state = result.get("final_state") or {}
        market = final_state.get("market_data") or {}
        if ticker and market.get("close") is not None:
            prices[ticker] = float(market["close"])
    return prices
