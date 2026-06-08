from __future__ import annotations

from typing import Any, Protocol


class ExecutionAdapter(Protocol):
    def apply_decision(self, run_id: str, state: dict[str, Any]) -> dict[str, Any]:
        """Apply the final workflow decision to an execution venue."""

    def apply_portfolio_plan(self, run_id: str, state: dict[str, Any]) -> dict[str, Any]:
        """Apply a portfolio-level execution plan to an execution venue."""
