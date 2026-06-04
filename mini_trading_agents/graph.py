from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from mini_trading_agents.logging import JsonlRunLogger, changed_keys, state_summary
from mini_trading_agents.state import TradingState


Node = Callable[[TradingState], TradingState]


@dataclass
class Workflow:
    """A small sequential state-graph runner.

    Each node receives the current shared state and returns updates. The runner
    merges those updates back into the same state, which mirrors the core
    information-sharing pattern used by graph-based agent workflows.
    """

    nodes: list[tuple[str, Node]] = field(default_factory=list)

    def add_node(self, name: str, node: Node) -> None:
        self.nodes.append((name, node))

    def run(self, state: TradingState, log_path: str | Path | None = None) -> TradingState:
        logger = JsonlRunLogger(Path(log_path)) if log_path else None
        if logger:
            logger.event("run_start", state=state_summary(state))

        for name, node in self.nodes:
            if logger:
                logger.event("node_start", node=name, state=state_summary(state))

            before = state.copy()
            updates = node(state)
            state.update(updates)
            state["trace"].append(name)

            if logger:
                logger.event(
                    "node_end",
                    node=name,
                    changed_keys=changed_keys(before, updates),
                    updates=updates,
                    state=state_summary(state),
                )

        if logger:
            logger.event("run_end", state=state)

        return state
