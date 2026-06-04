from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class SentimentDataAdapter(ABC):
    source_key: str

    @abstractmethod
    def fetch(self, ticker: str, as_of: str) -> dict[str, Any]:
        raise NotImplementedError
