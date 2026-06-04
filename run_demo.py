from __future__ import annotations

import argparse
import json

from mini_trading_agents.langgraph_workflow import build_demo_workflow, initial_state
from mini_trading_agents.logging import JsonlRunLogger, make_log_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the mini trading agents demo.")
    parser.add_argument("--ticker", default="NVDA", help="Ticker symbol to analyze.")
    parser.add_argument("--date", default="2026-01-15", help="Analysis date.")
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Print the complete shared state as JSON.",
    )
    parser.add_argument(
        "--log-dir",
        default="logs",
        help="Directory for JSONL audit logs. Use --no-log to disable.",
    )
    parser.add_argument(
        "--no-log",
        action="store_true",
        help="Disable JSONL audit logging.",
    )
    parser.add_argument(
        "--research-turns",
        type=int,
        default=4,
        help="Total bull/bear debate turns before the research manager runs.",
    )
    parser.add_argument(
        "--risk-turns",
        type=int,
        default=6,
        help="Total risk debate turns before the portfolio manager runs.",
    )
    args = parser.parse_args()

    graph = build_demo_workflow()
    state = initial_state(
        args.ticker,
        args.date,
        max_research_debate_turns=args.research_turns,
        max_risk_debate_turns=args.risk_turns,
    )
    log_path = None if args.no_log else make_log_path(args.log_dir, state["ticker"], state["analysis_date"])
    logger = JsonlRunLogger(log_path) if log_path else None
    if logger:
        logger.event("stream_start", state=state)

    final_state = state
    # The JSONL audit log is driven by LangGraph streaming rather than manual
    # node wrappers. "updates" records node-level partial state changes, while
    # "values" records full state snapshots after graph steps.
    for chunk in graph.stream(state, stream_mode=["updates", "values"], version="v2"):
        if logger:
            logger.stream_chunk(chunk)
        if chunk["type"] == "values":
            final_state = chunk["data"]

    if logger:
        logger.event("stream_end", state=final_state)
    state = final_state

    if args.pretty:
        print(json.dumps(state, indent=2, ensure_ascii=False))
        if log_path:
            print(f"\nLog file: {log_path}")
        return

    print(f"Ticker: {state['ticker']}")
    print(f"Date: {state['analysis_date']}")
    print(f"Final decision: {state['final_trade_decision']['action']}")
    print(f"Confidence: {state['final_trade_decision']['confidence']}")
    print(f"Position size: {state['final_trade_decision']['position_size']}")
    print(f"Reason: {state['final_trade_decision']['reason']}")
    if log_path:
        print(f"Log file: {log_path}")
    print()
    print("Trace:")
    for event in state["trace"]:
        print(f"- {event}")


if __name__ == "__main__":
    main()
