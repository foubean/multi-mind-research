from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from mini_trading_agents.data_layer.common import average, pct_change
from mini_trading_agents.data_layer.lineage import make_lineage
from mini_trading_agents.data_layer.market.base import MarketDataAdapter
from mini_trading_agents.data_layer.market.yahoo import _annualized_volatility, _ema, _market_observations, _rsi


class AlpacaMarketDataAdapter(MarketDataAdapter):
    source_key = "alpaca"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        config = config or {}
        self.api_key = str(config.get("api_key", "")) or os.getenv(str(config.get("api_key_env", "ALPACA_API_KEY")), "")
        self.api_secret = str(config.get("api_secret", "")) or os.getenv(
            str(config.get("api_secret_env", "ALPACA_API_SECRET")),
            "",
        )
        self.base_url = str(config.get("base_url", "https://data.alpaca.markets")).rstrip("/")
        self.feed = str(config.get("feed", "iex"))
        if not self.api_key or not self.api_secret:
            raise RuntimeError("Alpaca market data requires API key and secret.")

    def fetch(self, ticker: str, as_of: str) -> dict[str, Any]:
        bars = self._bars(ticker, as_of)
        if not bars:
            raise RuntimeError(f"Alpaca returned no market bars for {ticker}.")

        closes = [float(bar["c"]) for bar in bars]
        volumes = [int(bar.get("v", 0) or 0) for bar in bars]
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
            "source": "alpaca_market_data",
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
            "lineage": make_lineage(
                provider="alpaca",
                adapter="AlpacaMarketDataAdapter",
                raw_source=f"GET {self.base_url}/v2/stocks/{ticker}/bars?timeframe=1Day&feed={self.feed}",
                transforms=[
                    {"field": "close", "derived_from": ["bars[-1].c"], "method": "latest close"},
                    {"field": "change_pct", "derived_from": ["bars[-1].c", "bars[-2].c"], "method": "pct_change"},
                    {"field": "average_volume_20d", "derived_from": ["bars[-20:].v"], "method": "average"},
                    {"field": "moving_average_20", "derived_from": ["bars[-20:].c"], "method": "average"},
                    {"field": "moving_average_60", "derived_from": ["bars[-60:].c"], "method": "average"},
                    {"field": "rsi_14", "derived_from": ["bars.c"], "method": "rsi(period=14)"},
                    {"field": "macd", "derived_from": ["bars.c"], "method": "ema(12)-ema(26)"},
                    {"field": "volatility_20d", "derived_from": ["bars[-21:].c"], "method": "annualized volatility"},
                ],
                used_by="market_analyst",
            ),
        }

    def _bars(self, ticker: str, as_of: str) -> list[dict[str, Any]]:
        end = _parse_date(as_of) + timedelta(days=1)
        start = end - timedelta(days=210)
        query = urlencode(
            {
                "timeframe": "1Day",
                "start": start.isoformat(),
                "end": end.isoformat(),
                "limit": 200,
                "adjustment": "raw",
                "feed": self.feed,
            }
        )
        response = self._request("GET", f"/v2/stocks/{ticker.upper()}/bars?{query}")
        return response.get("bars", [])

    def _request(self, method: str, path: str) -> dict[str, Any]:
        request = Request(
            f"{self.base_url}{path}",
            method=method,
            headers={
                "APCA-API-KEY-ID": self.api_key,
                "APCA-API-SECRET-KEY": self.api_secret,
                "Accept": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=20) as response:
                content = response.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Alpaca market data HTTP {exc.code}: {detail[:500]}") from exc
        except URLError as exc:
            raise RuntimeError(f"Alpaca market data request failed: {exc}") from exc
        return json.loads(content) if content else {}


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()
