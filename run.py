from __future__ import annotations

import argparse
from contextlib import ExitStack, nullcontext
import json
from pathlib import Path
from uuid import uuid4

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.store.sqlite import SqliteStore as LangGraphSqliteStore

from mini_trading_agents.config import load_config
from mini_trading_agents.execution import build_execution_adapter
from mini_trading_agents.llm_adapter import get_llm_adapter
from mini_trading_agents.logging import JsonlRunLogger, make_log_path
from mini_trading_agents.reporting import make_report_path, write_html_report
from mini_trading_agents.storage import BusinessStore, SnapshotStore, build_decision_memory_event
from mini_trading_agents.workflow import build_demo_workflow, initial_state


DEFAULT_CONFIG = "config.toml"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run single-node single-ticker trading analysis.")
    parser.add_argument("--config", default=DEFAULT_CONFIG, help="TOML config file.")
    parser.add_argument("--ticker", help="Ticker symbol. Defaults to first value in [run].tickers.")
    parser.add_argument("--date", help="Analysis date. Empty string uses [run].analysis_date.")
    parser.add_argument("--pretty", action="store_true", help="Print the complete shared state as JSON.")
    parser.add_argument("--log-dir", help="Directory for JSONL audit logs. Defaults to [logging].log_dir.")
    parser.add_argument("--log", dest="log_enabled", action="store_true", default=None, help="Enable JSONL audit logging.")
    parser.add_argument("--no-log", dest="log_enabled", action="store_false", help="Disable JSONL audit logging.")
    parser.add_argument("--research-turns", type=int, help="Override [run].research_turns.")
    parser.add_argument("--risk-turns", type=int, help="Override [run].risk_turns.")
    parser.add_argument("--data-provider", choices=["sample", "yahoo"], help="Shortcut provider for all data categories.")
    parser.add_argument("--market-provider", choices=["sample", "yahoo", "alpaca"], help="Provider for market data.")
    parser.add_argument("--sentiment-provider", choices=["sample", "yahoo"], help="Provider for sentiment data.")
    parser.add_argument("--news-provider", choices=["sample", "yahoo"], help="Provider for news data.")
    parser.add_argument("--fundamentals-provider", choices=["sample", "yahoo"], help="Provider for fundamentals data.")
    parser.add_argument("--run-id", help="Stable run id for snapshots and decision memory.")
    parser.add_argument("--resume", help="Load the latest complete state snapshot for the given run id.")
    parser.add_argument("--rerun-resume", action="store_true", help="Run the graph again after loading --resume state.")
    parser.add_argument("--storage-path", help="Override [persistence].storage_path.")
    args = parser.parse_args()

    app_config = load_config(args.config)
    persistence = app_config.persistence
    run_config = app_config.run
    logging_config = app_config.logging
    reporting = app_config.reporting

    ticker = (args.ticker or run_config.tickers[0]).upper()
    analysis_date = _resolve_cli_date(args.date, run_config.analysis_date)
    research_turns = args.research_turns if args.research_turns is not None else run_config.research_turns
    risk_turns = args.risk_turns if args.risk_turns is not None else run_config.risk_turns
    log_enabled = logging_config.log_enabled if args.log_enabled is None else args.log_enabled
    log_dir = args.log_dir or logging_config.log_dir
    storage_path = args.storage_path or persistence.storage_path

    snapshot_store = SnapshotStore(persistence.snapshot_path) if persistence.snapshot_enabled else None
    business_store = (
        BusinessStore(storage_path) if persistence.decision_memory_enabled or app_config.paper_trading.enable else None
    )
    run_id = args.resume or args.run_id or f"{ticker}-{analysis_date}-{uuid4().hex[:8]}"

    if args.resume:
        if not snapshot_store:
            raise SystemExit("Resume requires snapshot_enabled = true.")
        state = snapshot_store.latest_snapshot(args.resume)
        if state is None:
            raise SystemExit(f"No snapshot found for run id: {args.resume}")
    else:
        state = initial_state(
            ticker,
            analysis_date,
            max_research_debate_turns=research_turns,
            max_risk_debate_turns=risk_turns,
            data_providers=_resolve_data_providers(app_config, args),
            data_provider_config=_data_provider_config(),
            trade_preferences=app_config.trade_preferences.__dict__,
            llm_config=app_config.llm.__dict__,
        )

    if args.resume and not args.rerun_resume:
        _print_state(
            state,
            run_id,
            storage_path if business_store else None,
            persistence.snapshot_path if snapshot_store else None,
            persistence.checkpoint_path if persistence.checkpoint_enabled else None,
            persistence.memory_store_path if persistence.decision_memory_enabled else None,
            log_path=None,
            pretty=args.pretty,
        )
        return

    _run_llm_runtime_check(app_config.llm.__dict__)

    if snapshot_store:
        snapshot_store.create_or_update_run(run_id, state)
    if business_store and persistence.decision_memory_enabled:
        business_store.create_or_update_run(run_id, state)

    log_path = make_log_path(log_dir, state["ticker"], state["analysis_date"]) if log_enabled else None
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
        for chunk in graph.stream(state, config=graph_config, stream_mode=["updates", "values"], version="v2"):
            if logger:
                logger.stream_chunk(chunk)
            if chunk["type"] == "values":
                final_state = chunk["data"]
                if snapshot_store:
                    snapshot_store.save_snapshot(run_id, step_index, final_state)
                step_index += 1

        if persistence.decision_memory_enabled:
            _save_store_memory(memory_store, run_id, final_state)

    if app_config.paper_trading.enable:
        paper_adapter = build_execution_adapter(app_config.paper_trading)
        final_state["paper_trading_result"] = paper_adapter.apply_decision(run_id, final_state)

    if logger:
        logger.event("stream_end", run_id=run_id, state=final_state)
    if snapshot_store:
        snapshot_store.mark_completed(run_id, final_state)
    if business_store and persistence.decision_memory_enabled:
        business_store.mark_completed(run_id, final_state)
        business_store.save_decision_memory(run_id, final_state)

    report_path = make_report_path(reporting.report_dir, final_state["ticker"], final_state["analysis_date"])
    write_html_report(report_path, final_state, run_id)

    _print_state(
        final_state,
        run_id,
        storage_path if business_store else None,
        persistence.snapshot_path if snapshot_store else None,
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
    try:
        get_llm_adapter(llm_config).check_connection()
    except Exception as exc:
        raise SystemExit(
            "LLM runtime check failed before workflow execution: "
            f"{type(exc).__name__}: {str(exc)[:500]}"
        ) from exc


def _resolve_data_providers(app_config, args) -> dict:
    provider_config = app_config.data_providers
    default_provider = args.data_provider or provider_config.default
    return {
        "market": args.market_provider or provider_config.market or default_provider,
        "sentiment": args.sentiment_provider or provider_config.sentiment or default_provider,
        "news": args.news_provider or provider_config.news or default_provider,
        "fundamentals": args.fundamentals_provider or provider_config.fundamentals or default_provider,
    }


def _resolve_cli_date(cli_date: str | None, config_date: str) -> str:
    if cli_date is None:
        return config_date
    return cli_date.strip() or config_date


def _data_provider_config() -> dict:
    return {"market": {"base_url": "https://data.alpaca.markets", "feed": "iex"}}


def _print_state(
    state: dict,
    run_id: str,
    storage_path: str | None,
    snapshot_path: str | None,
    checkpoint_path: str | None,
    memory_store_path: str | None,
    log_path,
    pretty: bool,
    report_path=None,
) -> None:
    if pretty:
        print(json.dumps(state, indent=2, ensure_ascii=False))
        print(f"\nRun id: {run_id}")
    else:
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
    print(f"Storage: {storage_path or 'disabled'}")
    print(f"Snapshot: {snapshot_path or 'disabled'}")
    print(f"Checkpoint: {checkpoint_path or 'disabled'}")
    print(f"Memory store: {memory_store_path or 'disabled'}")
    if report_path:
        print(f"HTML report: {report_path}")
    if log_path:
        print(f"Log file: {log_path}")
    print("Trace:")
    for event in state.get("trace", []):
        print(f"- {event}")


if __name__ == "__main__":
    main()
