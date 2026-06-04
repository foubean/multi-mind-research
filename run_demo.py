from __future__ import annotations

import argparse
import json

from mini_trading_agents.logging import make_log_path
from mini_trading_agents.workflow import build_demo_workflow, initial_state


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
    args = parser.parse_args()

    workflow = build_demo_workflow()
    state = initial_state(args.ticker, args.date)
    log_path = None if args.no_log else make_log_path(args.log_dir, state["ticker"], state["analysis_date"])
    state = workflow.run(state, log_path=log_path)

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
