from __future__ import annotations

import argparse
from contextlib import ExitStack, nullcontext
import json
from pathlib import Path
from uuid import uuid4

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.store.sqlite import SqliteStore as LangGraphSqliteStore

from mini_trading_agents.config import DEFAULT_CONFIG_PATH, load_config
from mini_trading_agents.execution import build_execution_adapter
from mini_trading_agents.langgraph_workflow import build_demo_workflow, initial_state
from mini_trading_agents.llm_adapter import get_llm_adapter
from mini_trading_agents.logging import JsonlRunLogger, make_log_path
from mini_trading_agents.reporting import make_report_path, write_html_report
from mini_trading_agents.storage import SqliteStore, build_decision_memory_event


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
        "--config",
        default=DEFAULT_CONFIG_PATH,
        help="TOML config file for persistence features.",
    )
    parser.add_argument(
        "--storage-path",
        help="Override config persistence.storage_path for snapshots and decision memory.",
    )
    args = parser.parse_args()

    app_config = load_config(args.config)
    persistence = app_config.persistence
    storage_path = args.storage_path or persistence.storage_path
    store = SqliteStore(storage_path) if persistence.snapshot_enabled or persistence.decision_memory_enabled else None
    run_id = args.resume or args.run_id or f"{args.ticker.upper()}-{args.date}-{uuid4().hex[:8]}"
    if args.resume:
        if not store or not persistence.snapshot_enabled:
            raise SystemExit("Resume requires snapshot_enabled = true.")
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
            runtime_parameters=app_config.parameters.__dict__,
            trade_preferences=app_config.trade_preferences.__dict__,
            llm_config=app_config.llm.__dict__,
        )
    if args.resume and not args.rerun_resume:
        _print_state(
            state,
            run_id,
            storage_path if store else None,
            persistence.checkpoint_path if persistence.checkpoint_enabled else None,
            persistence.memory_store_path if persistence.decision_memory_enabled else None,
            log_path=None,
            pretty=args.pretty,
        )
        return

    _run_llm_runtime_check(app_config.llm.__dict__)

    if store and (persistence.snapshot_enabled or persistence.decision_memory_enabled):
        store.create_or_update_run(run_id, state)

    log_path = None if args.no_log else make_log_path(args.log_dir, state["ticker"], state["analysis_date"])
    logger = JsonlRunLogger(log_path) if log_path else None
    if logger:
        logger.event("stream_start", run_id=run_id, state=state)

    final_state = state
    step_index = 0
    with ExitStack() as stack:
        checkpointer = stack.enter_context(_checkpoint_context(persistence.checkpoint_enabled, persistence.checkpoint_path))
        memory_store = stack.enter_context(
            _memory_store_context(persistence.decision_memory_enabled, persistence.memory_store_path)
        )
        graph = build_demo_workflow(checkpointer=checkpointer, store=memory_store)
        graph_config = {"configurable": {"thread_id": run_id}} if checkpointer else None
        # The JSONL audit log is driven by LangGraph streaming rather than manual
        # node wrappers. "updates" records node-level partial state changes, while
        # "values" records full state snapshots after graph steps.
        for chunk in graph.stream(state, config=graph_config, stream_mode=["updates", "values"], version="v2"):
            if logger:
                logger.stream_chunk(chunk)
            if chunk["type"] == "values":
                final_state = chunk["data"]
                if store and persistence.snapshot_enabled:
                    store.save_snapshot(run_id, step_index, final_state)
                step_index += 1

        if persistence.decision_memory_enabled:
            _save_store_memory(memory_store, run_id, final_state)

    if app_config.paper_trading.enabled:
        paper_adapter = build_execution_adapter(
            app_config.paper_trading,
            storage_path=storage_path,
        )
        final_state["paper_trading_result"] = paper_adapter.apply_decision(run_id, final_state)

    if logger:
        logger.event("stream_end", run_id=run_id, state=final_state)
    if store and (persistence.snapshot_enabled or persistence.decision_memory_enabled):
        store.mark_completed(run_id, final_state)
    if store and persistence.decision_memory_enabled:
        store.save_decision_memory(run_id, final_state)
    state = final_state
    report_path = make_report_path("reports", state["ticker"], state["analysis_date"])
    write_html_report(report_path, state, run_id)

    _print_state(
        state,
        run_id,
        storage_path if store else None,
        persistence.checkpoint_path if persistence.checkpoint_enabled else None,
        persistence.memory_store_path if persistence.decision_memory_enabled else None,
        log_path=log_path,
        report_path=report_path,
        pretty=args.pretty,
    )


def _checkpoint_context(enabled: bool, checkpoint_path: str):
    if not enabled:
        return nullcontext(None)
    Path(checkpoint_path).parent.mkdir(parents=True, exist_ok=True)
    return SqliteSaver.from_conn_string(checkpoint_path)


def _memory_store_context(enabled: bool, memory_store_path: str):
    if not enabled:
        return nullcontext(None)
    Path(memory_store_path).parent.mkdir(parents=True, exist_ok=True)
    return LangGraphSqliteStore.from_conn_string(memory_store_path)


def _save_store_memory(memory_store, run_id: str, state: dict) -> None:
    if memory_store is None or not state.get("final_trade_decision"):
        return
    event = build_decision_memory_event(run_id, state)
    namespace = ("decision_memory", event["scope_type"], event["scope_id"])
    key = f"{event['analysis_date']}:{run_id}"
    memory_store.put(namespace, key, event)


def _run_llm_runtime_check(llm_config: dict) -> None:
    if not llm_config.get("enabled") or not llm_config.get("runtime_check_enabled", True):
        return
    try:
        get_llm_adapter(llm_config).check_connection()
    except Exception as exc:
        raise SystemExit(
            "LLM runtime check failed before workflow execution: "
            f"{type(exc).__name__}: {str(exc)[:500]}"
        ) from exc


def _print_state(
    state: dict,
    run_id: str,
    storage_path: str | None,
    checkpoint_path: str | None,
    memory_store_path: str | None,
    log_path,
    pretty: bool,
    report_path=None,
) -> None:
    if pretty:
        print(json.dumps(state, indent=2, ensure_ascii=False))
        print(f"\nRun id: {run_id}")
        print(f"Storage: {storage_path or 'disabled'}")
        print(f"Checkpoint: {checkpoint_path or 'disabled'}")
        print(f"Memory store: {memory_store_path or 'disabled'}")
        if report_path:
            print(f"HTML report: {report_path}")
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
    trade_advice = state.get("trade_advice")
    if trade_advice:
        print("Trade advice:")
        print(f"- risk profile: {trade_advice['risk_profile']}")
        print(f"- trading style: {trade_advice['trading_style']}")
        print(f"- expected return: {trade_advice['expected_return_pct']}")
        print(f"- expected risk: {trade_advice['expected_risk_pct']}")
    llm_usage_trace = state.get("llm_usage_trace")
    if llm_usage_trace:
        print("LLM usage:")
        for item in llm_usage_trace:
            detail = f"{item['node']}: {item['status']} ({item.get('model')})"
            if item.get("error_type"):
                detail += f" - {item['error_type']}: {item.get('error')}"
            print(f"- {detail}")
    paper_result = state.get("paper_trading_result")
    if paper_result:
        print("Paper trading:")
        print(f"- status: {paper_result['status']}")
        print(f"- provider: {paper_result.get('provider', 'local')}")
        print(f"- account: {paper_result['account_id']}")
        print(f"- equity: {paper_result['equity']}")
        print(f"- cash: {paper_result['cash']}")
        print(f"- position: {paper_result['position_quantity']} {paper_result['ticker']}")
    print(f"Storage: {storage_path or 'disabled'}")
    print(f"Checkpoint: {checkpoint_path or 'disabled'}")
    print(f"Memory store: {memory_store_path or 'disabled'}")
    if report_path:
        print(f"HTML report: {report_path}")
    if log_path:
        print(f"Log file: {log_path}")
    print()
    print("Trace:")
    for event in state["trace"]:
        print(f"- {event}")


if __name__ == "__main__":
    main()
