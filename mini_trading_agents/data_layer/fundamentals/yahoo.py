from __future__ import annotations

from typing import Any

from mini_trading_agents.data_layer.common import safe_float, safe_ratio, yfinance_client
from mini_trading_agents.data_layer.fundamentals.base import FundamentalsDataAdapter


class YahooFundamentalsDataAdapter(FundamentalsDataAdapter):
    source_key = "yahoo"

    def fetch(self, ticker: str, as_of: str) -> dict[str, Any]:
        yf = yfinance_client()
        ticker_obj = yf.Ticker(ticker)
        info = ticker_obj.info or {}
        financials = ticker_obj.financials
        balance_sheet = ticker_obj.balance_sheet
        cashflow = ticker_obj.cashflow

        revenue_growth_yoy = safe_float(info.get("revenueGrowth"))
        gross_margin = safe_float(info.get("grossMargins"))
        operating_margin = safe_float(info.get("operatingMargins"))
        pe_ratio = safe_float(info.get("trailingPE"))
        forward_pe = safe_float(info.get("forwardPE"))
        debt_to_equity = safe_float(info.get("debtToEquity")) / 100
        free_cash_flow = safe_float(info.get("freeCashflow"))
        cash_and_equivalents = safe_float(info.get("totalCash"))

        revenue_from_statement = _latest_statement_value(financials, ["Total Revenue", "Operating Revenue"])
        gross_profit = _latest_statement_value(financials, ["Gross Profit"])
        operating_income = _latest_statement_value(financials, ["Operating Income"])
        total_debt = _latest_statement_value(balance_sheet, ["Total Debt", "Long Term Debt"])
        stockholders_equity = _latest_statement_value(balance_sheet, ["Stockholders Equity", "Total Equity Gross Minority Interest"])
        free_cash_flow_statement = _latest_statement_value(cashflow, ["Free Cash Flow"])
        cash_statement = _latest_statement_value(balance_sheet, ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"])

        if gross_margin == 0 and revenue_from_statement:
            gross_margin = safe_ratio(gross_profit, revenue_from_statement)
        if operating_margin == 0 and revenue_from_statement:
            operating_margin = safe_ratio(operating_income, revenue_from_statement)
        if debt_to_equity == 0:
            debt_to_equity = safe_ratio(total_debt, stockholders_equity)
        if free_cash_flow == 0:
            free_cash_flow = free_cash_flow_statement
        if cash_and_equivalents == 0:
            cash_and_equivalents = cash_statement

        if all(value == 0 for value in [revenue_growth_yoy, gross_margin, operating_margin, pe_ratio, forward_pe]):
            raise RuntimeError(f"Yahoo Finance returned insufficient fundamentals for {ticker}.")

        return {
            "ticker": ticker,
            "as_of": as_of,
            "source": "yahoo_finance",
            "revenue_growth_yoy": round(revenue_growth_yoy, 4),
            "gross_margin": round(gross_margin, 4),
            "operating_margin": round(operating_margin, 4),
            "pe_ratio": round(pe_ratio, 4),
            "forward_pe": round(forward_pe, 4),
            "debt_to_equity": round(debt_to_equity, 4),
            "free_cash_flow": round(free_cash_flow, 2),
            "cash_and_equivalents": round(cash_and_equivalents, 2),
            "observations": _fundamentals_observations(
                revenue_growth_yoy,
                gross_margin,
                operating_margin,
                pe_ratio,
                forward_pe,
                debt_to_equity,
                free_cash_flow,
            ),
        }


def _latest_statement_value(statement: Any, labels: list[str]) -> float:
    if statement is None or getattr(statement, "empty", True):
        return 0.0
    for label in labels:
        if label in statement.index:
            values = statement.loc[label].dropna()
            if not values.empty:
                return safe_float(values.iloc[0])
    return 0.0


def _fundamentals_observations(
    revenue_growth_yoy: float,
    gross_margin: float,
    operating_margin: float,
    pe_ratio: float,
    forward_pe: float,
    debt_to_equity: float,
    free_cash_flow: float,
) -> list[str]:
    observations = [
        f"Revenue growth year over year is {revenue_growth_yoy:.2%}.",
        f"Gross margin is {gross_margin:.2%}; operating margin is {operating_margin:.2%}.",
        f"Trailing P/E is {pe_ratio:.2f}; forward P/E is {forward_pe:.2f}.",
        f"Debt to equity is {debt_to_equity:.2f}.",
    ]
    if free_cash_flow > 0:
        observations.append("Free cash flow is positive.")
    elif free_cash_flow < 0:
        observations.append("Free cash flow is negative.")
    else:
        observations.append("Free cash flow was unavailable or zero in Yahoo data.")
    return observations
