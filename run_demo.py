from __future__ import annotations

import argparse
import json
from uuid import uuid4

from mini_trading_agents.langgraph_workflow import build_demo_workflow, initial_state
from mini_trading_agents.logging import JsonlRunLogger, make_log_path
from mini_trading_agents.storage import SqliteStore


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
    parser.add_argument(
        "--data-provider",
        choices=["sample", "yahoo"],
        default="sample",
        help="Shortcut provider for all data categories.",
    )
    parser.add_argument(
        "--market-provider",
        choices=["sample", "yahoo"],
        help="Provider for market data. Defaults to --data-provider.",
    )
    parser.add_argument(
        "--sentiment-provider",
        choices=["sample", "yahoo"],
        help="Provider for sentiment data. Defaults to --data-provider.",
    )
    parser.add_argument(
        "--news-provider",
        choices=["sample", "yahoo"],
        help="Provider for news data. Defaults to --data-provider.",
    )
    parser.add_argument(
        "--fundamentals-provider",
        choices=["sample", "yahoo"],
        help="Provider for fundamentals data. Defaults to --data-provider.",
    )
    parser.add_argument(
        "--run-id",
        help="Stable run id for snapshots and decision memory. Generated when omitted.",
    )
    parser.add_argument(
        "--resume",
        help="Load the latest complete state snapshot for the given run id.",
    )
    parser.add_argument(
        "--rerun-resume",
        action="store_true",
        help="After --resume loads the latest snapshot, run the graph again from that state.",
    )
    parser.add_argument(
        "--storage-path",
        default="storage/trading_agents.sqlite",
        help="SQLite path for workflow snapshots and decision memory.",
    )
    args = parser.parse_args()

    graph = build_demo_workflow()
    store = SqliteStore(args.storage_path)
    run_id = args.resume or args.run_id or f"{args.ticker.upper()}-{args.date}-{uuid4().hex[:8]}"
    if args.resume:
        state = store.latest_snapshot(args.resume)
        if state is None:
            raise SystemExit(f"No snapshot found for run id: {args.resume}")
    else:
        data_providers = {
            "market": args.market_provider or args.data_provider,
            "sentiment": args.sentiment_provider or args.data_provider,
            "news": args.news_provider or args.data_provider,
            "fundamentals": args.fundamentals_provider or args.data_provider,
        }
        state = initial_state(
            args.ticker,
            args.date,
            max_research_debate_turns=args.research_turns,
            max_risk_debate_turns=args.risk_turns,
            data_providers=data_providers,
        )
    if args.resume and not args.rerun_resume:
        _print_state(state, run_id, args.storage_path, log_path=None, pretty=args.pretty)
        return

    store.create_or_update_run(run_id, state)

    log_path = None if args.no_log else make_log_path(args.log_dir, state["ticker"], state["analysis_date"])
    logger = JsonlRunLogger(log_path) if log_path else None
    if logger:
        logger.event("stream_start", run_id=run_id, state=state)

    final_state = state
    step_index = 0
    # The JSONL audit log is driven by LangGraph streaming rather than manual
    # node wrappers. "updates" records node-level partial state changes, while
    # "values" records full state snapshots after graph steps.
    for chunk in graph.stream(state, stream_mode=["updates", "values"], version="v2"):
        if logger:
            logger.stream_chunk(chunk)
        if chunk["type"] == "values":
            final_state = chunk["data"]
            store.save_snapshot(run_id, step_index, final_state)
            step_index += 1

    if logger:
        logger.event("stream_end", run_id=run_id, state=final_state)
    store.mark_completed(run_id, final_state)
    store.save_decision_memory(run_id, final_state)
    state = final_state

    _print_state(state, run_id, args.storage_path, log_path=log_path, pretty=args.pretty)


def _print_state(
    state: dict,
    run_id: str,
    storage_path: str,
    log_path,
    pretty: bool,
) -> None:
    if pretty:
        print(json.dumps(state, indent=2, ensure_ascii=False))
        print(f"\nRun id: {run_id}")
        print(f"Storage: {storage_path}")
        if log_path:
            print(f"\nLog file: {log_path}")
        return

    print(f"Run id: {run_id}")
    print(f"Ticker: {state['ticker']}")
    print(f"Date: {state['analysis_date']}")
    decision = state.get("final_trade_decision")
    if decision:
        print(f"Final decision: {decision['action']}")
        print(f"Confidence: {decision['confidence']}")
        print(f"Position size: {decision['position_size']}")
        print(f"Reason: {decision['reason']}")
    else:
        print("Final decision: not available in this snapshot")
    data_status = state.get("data_status")
    if data_status:
        print(f"Data status: {data_status['status']} ({data_status['providers']})")
    print(f"Storage: {storage_path}")
    if log_path:
        print(f"Log file: {log_path}")
    print()
    print("Trace:")
    for event in state["trace"]:
        print(f"- {event}")


if __name__ == "__main__":
    main()
