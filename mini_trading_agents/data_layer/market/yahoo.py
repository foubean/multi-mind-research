from __future__ import annotations

from math import sqrt
from typing import Any

from mini_trading_agents.data_layer.common import average, pct_change, yfinance_client
from mini_trading_agents.data_layer.market.base import MarketDataAdapter


class YahooMarketDataAdapter(MarketDataAdapter):
    source_key = "yahoo"

    def fetch(self, ticker: str, as_of: str) -> dict[str, Any]:
        yf = yfinance_client()
        history = yf.Ticker(ticker).history(period="6mo", interval="1d", auto_adjust=False)
        if history.empty:
            raise RuntimeError(f"Yahoo Finance returned no historical data for {ticker}.")

        history = history.dropna(subset=["Close"])
        if history.empty:
            raise RuntimeError(f"Yahoo Finance historical data for {ticker} has no usable close prices.")

        closes = [float(value) for value in history["Close"].tolist()]
        volumes = [int(value) for value in history["Volume"].fillna(0).tolist()]
        latest_close = closes[-1]
        previous_close = closes[-2] if len(closes) > 1 else latest_close

        ma20 = average(closes[-20:])
        ma60 = average(closes[-60:])
        avg_volume_20 = average([float(value) for value in volumes[-20:]])
        rsi14 = _rsi(closes, period=14)
        macd = _ema(closes, 12) - _ema(closes, 26)
        volatility_20d = _annualized_volatility(closes[-21:])

        return {
            "ticker": ticker,
            "as_of": as_of,
            "source": "yahoo_finance",
            "close": round(latest_close, 4),
            "change_pct": round(pct_change(latest_close, previous_close), 4),
            "volume": volumes[-1],
            "average_volume_20d": round(avg_volume_20, 2),
            "moving_average_20": round(ma20, 4),
            "moving_average_60": round(ma60, 4),
            "rsi_14": round(rsi14, 4),
            "macd": round(macd, 4),
            "volatility_20d": round(volatility_20d, 4),
            "observations": _market_observations(
                latest_close,
                ma20,
                ma60,
                volumes[-1],
                avg_volume_20,
                rsi14,
                volatility_20d,
            ),
        }


def _ema(values: list[float], period: int) -> float:
    if not values:
        return 0.0
    multiplier = 2 / (period + 1)
    ema = values[0]
    for value in values[1:]:
        ema = (value - ema) * multiplier + ema
    return ema


def _rsi(values: list[float], period: int) -> float:
    if len(values) <= period:
        return 50.0
    deltas = [values[index] - values[index - 1] for index in range(1, len(values))]
    recent = deltas[-period:]
    gains = [delta for delta in recent if delta > 0]
    losses = [-delta for delta in recent if delta < 0]
    average_gain = average(gains)
    average_loss = average(losses)
    if average_loss == 0:
        return 100.0
    relative_strength = average_gain / average_loss
    return 100 - (100 / (1 + relative_strength))


def _annualized_volatility(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    returns = [pct_change(values[index], values[index - 1]) / 100 for index in range(1, len(values))]
    average_return = average(returns)
    variance = average([(value - average_return) ** 2 for value in returns])
    return sqrt(variance) * sqrt(252)


def _market_observations(
    close: float,
    ma20: float,
    ma60: float,
    volume: int,
    avg_volume_20: float,
    rsi14: float,
    volatility_20d: float,
) -> list[str]:
    trend = "above" if close >= ma20 and close >= ma60 else "below"
    participation = "above" if volume >= avg_volume_20 else "below"
    if rsi14 >= 70:
        momentum = "RSI is in an overbought zone."
    elif rsi14 <= 30:
        momentum = "RSI is in an oversold zone."
    else:
        momentum = "RSI is not in an extreme zone."
    return [
        f"Price is {trend} the 20-day and 60-day moving averages.",
        f"Latest volume is {participation} the 20-day average volume.",
        momentum,
        f"Annualized 20-day volatility is {volatility_20d:.2%}.",
    ]
