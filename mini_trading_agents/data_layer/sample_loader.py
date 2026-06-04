from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SAMPLE_DIR = Path(__file__).resolve().parents[2] / "sample"


def load_sample_data(filename: str, ticker: str, as_of: str) -> dict[str, Any]:
    with (SAMPLE_DIR / filename).open(encoding="utf-8") as file:
        data = json.load(file)
    data["ticker"] = ticker
    data["as_of"] = as_of
    return data
