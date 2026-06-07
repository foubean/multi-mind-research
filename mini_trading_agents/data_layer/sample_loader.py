from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mini_trading_agents.data_layer.lineage import make_lineage


SAMPLE_DIR = Path(__file__).resolve().parents[2] / "sample"


def load_sample_data(filename: str, ticker: str, as_of: str) -> dict[str, Any]:
    with (SAMPLE_DIR / filename).open(encoding="utf-8") as file:
        data = json.load(file)
    data["ticker"] = ticker
    data["as_of"] = as_of
    data["lineage"] = make_lineage(
        provider="sample",
        adapter="SampleDataAdapter",
        raw_source="local sample json",
        raw_ref=str(SAMPLE_DIR / filename),
        transforms=_sample_transforms(filename),
        used_by=str(data.get("used_by", "")),
    )
    return data


def _sample_transforms(filename: str) -> list[dict[str, Any]]:
    transforms_by_file = {
        "market_data.sample.json": [
            {"field": "change_pct", "derived_from": ["close"], "method": "precomputed sample value"},
            {"field": "moving_average_20", "derived_from": ["close"], "method": "precomputed sample value"},
            {"field": "moving_average_60", "derived_from": ["close"], "method": "precomputed sample value"},
            {"field": "rsi_14", "derived_from": ["close"], "method": "precomputed sample value"},
            {"field": "volatility_20d", "derived_from": ["close"], "method": "precomputed sample value"},
        ],
        "sentiment_data.sample.json": [
            {"field": "sentiment_score", "derived_from": ["positive_mentions", "negative_mentions"], "method": "precomputed sample value"},
            {"field": "mention_change_pct_24h", "derived_from": ["mention counts"], "method": "precomputed sample value"},
        ],
        "news_data.sample.json": [
            {"field": "items", "derived_from": ["sample news items"], "method": "normalized local sample records"},
            {"field": "sentiment", "derived_from": ["title", "summary"], "method": "precomputed sample labels"},
        ],
        "fundamentals_data.sample.json": [
            {"field": "revenue_growth_yoy", "derived_from": ["sample fundamentals"], "method": "precomputed sample value"},
            {"field": "operating_margin", "derived_from": ["sample fundamentals"], "method": "precomputed sample value"},
            {"field": "debt_to_equity", "derived_from": ["sample fundamentals"], "method": "precomputed sample value"},
        ],
    }
    return transforms_by_file.get(filename, [])
