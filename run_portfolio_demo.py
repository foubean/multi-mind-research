from __future__ import annotations

import argparse
from contextlib import ExitStack, nullcontext
from pathlib import Path
from uuid import uuid4

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.store.sqlite import SqliteStore as LangGraphSqliteStore

from mini_trading_agents.config import DEFAULT_CONFIG_PATH, load_config
from mini_trading_agents.execution import build_execution_adapter
from mini_trading_agents.llm_adapter import get_llm_adapter
from mini_trading_agents.portfolio_graph import build_portfolio_workflow, initial_portfolio_state
from mini_trading_agents.portfolio_graph.report import make_portfolio_report_path, write_portfolio_html_report
from mini_trading_agents.storage import SqliteStore, build_portfolio_memory_event


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the global portfolio graph demo.")
    parser.add_argument("--tickers", default="NVDA,AAPL,MSFT", help="Comma-separated ticker list.")
    parser.add_argument("--date", default="2026-01-15", help="Analysis date.")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="TOML config file.")
    parser.add_argument("--run-id", help="Stable portfolio run id. Generated when omitted.")
    parser.add_argument("--data-provider", choices=["sample", "yahoo"], default="sample")
    parser.add_argument("--report-dir", default="reports")
    parser.add_argument(
        "--execute-paper",
        action="store_true",
        help="Submit the generated execution plan to the configured paper trading adapter.",
    )
    args = parser.parse_args()

    app_config = load_config(args.config)
    persistence = app_config.persistence
    storage = SqliteStore(persistence.storage_path) if persistence.snapshot_enabled or persistence.decision_memory_enabled else None
    _run_llm_runtime_check(app_config.llm.__dict__)

    tickers = [ticker.strip().upper() for ticker in args.tickers.split(",") if ticker.strip()]
    run_id = args.run_id or f"PORTFOLIO-{args.date}-{uuid4().hex[:8]}"
    providers = {
        "market": args.data_provider,
        "sentiment": args.data_provider,
        "news": args.data_provider,
        "fundamentals": args.data_provider,
    }
    state = initial_portfolio_state(
        run_id=run_id,
        tickers=tickers,
        analysis_date=args.date,
        data_providers=providers,
        app_config=app_config,
    )
    if storage and (persistence.snapshot_enabled or persistence.decision_memory_enabled):
        storage.create_or_update_run(run_id, state)

    final_state = state
    step_index = 0
    with ExitStack() as stack:
        checkpointer = stack.enter_context(_checkpoint_context(persistence.checkpoint_enabled, persistence.checkpoint_path))
        memory_store = stack.enter_context(
            _memory_store_context(persistence.decision_memory_enabled, persistence.memory_store_path)
        )
        graph = build_portfolio_workflow(checkpointer=checkpointer, store=memory_store)
        graph_config = {"configurable": {"thread_id": run_id}} if checkpointer else None
        for chunk in graph.stream(state, config=graph_config, stream_mode=["updates", "values"], version="v2"):
            if chunk["type"] == "values":
                final_state = chunk["data"]
                if storage and persistence.snapshot_enabled:
                    storage.save_snapshot(run_id, step_index, final_state)
                step_index += 1
        if persistence.decision_memory_enabled:
            _save_portfolio_store_memory(memory_store, run_id, final_state)

    if storage and (persistence.snapshot_enabled or persistence.decision_memory_enabled):
        storage.mark_completed(run_id, final_state)
    if storage and persistence.decision_memory_enabled:
        storage.save_portfolio_memory(run_id, final_state)

    if args.execute_paper:
        if not app_config.paper_trading.enabled:
            raise SystemExit("--execute-paper requires [paper_trading].enabled = true.")
        if final_state.get("rejected_plan"):
            raise SystemExit("Paper execution skipped because the portfolio plan was rejected.")
        if not (final_state.get("validation_result") or {}).get("valid"):
            raise SystemExit("Paper execution skipped because portfolio validation is not valid.")
        if not (final_state.get("execution_validation_result") or {}).get("valid"):
            raise SystemExit("Paper execution skipped because execution validation is not valid.")
        paper_adapter = build_execution_adapter(app_config.paper_trading, storage_path=persistence.storage_path)
        final_state["paper_trading_result"] = paper_adapter.apply_portfolio_plan(run_id, final_state)
        if storage:
            storage.mark_completed(run_id, final_state)
            storage.save_trade_outcomes_from_paper_execution(run_id, final_state)

    report_path = make_portfolio_report_path(args.report_dir, run_id)
    write_portfolio_html_report(report_path, final_state)

    _print_state(final_state, report_path)


def _run_llm_runtime_check(llm_config: dict) -> None:
    if not llm_config.get("enabled") or not llm_config.get("runtime_check_enabled", True):
        return
    adapter = get_llm_adapter(llm_config)
    adapter.check_connection()


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


def _save_portfolio_store_memory(memory_store, run_id: str, state: dict) -> None:
    if memory_store is None or not state.get("portfolio_plan"):
        return
    event = build_portfolio_memory_event(run_id, state)
    namespace = ("decision_memory", event["scope_type"], event["scope_id"])
    key = f"{event['analysis_date']}:{run_id}"
    memory_store.put(namespace, key, event)


def _print_state(state: dict, report_path) -> None:
    plan = state.get("portfolio_plan") or {}
    execution = state.get("execution_plan") or {}
    print(f"Run id: {state['run_id']}")
    print(f"Tickers: {', '.join(state['tickers'])}")
    print(f"Decision: {plan.get('decision', state.get('rejected_plan', {}).get('status', 'N/A'))}")
    if plan.get("target_weights"):
        print("Target weights:")
        for ticker, weight in sorted(plan["target_weights"].items()):
            print(f"- {ticker}: {weight:.1%}")
    if execution.get("orders"):
        print("Orders:")
        for order in execution["orders"]:
            print(f"- {order['side']} {order['ticker']} to {order['target_weight']:.1%}")
    paper = state.get("paper_trading_result")
    if paper:
        print("Paper execution:")
        print(f"- provider: {paper.get('provider')}")
        print(f"- status: {paper.get('status')}")
        print(f"- account: {paper.get('account_id')}")
        for order in paper.get("orders", []):
            print(f"- {order.get('ticker')}: {order.get('status')} {order.get('order_id', '')}")
    print(f"Validation: {(state.get('validation_result') or state.get('preflight_result') or {}).get('status', 'N/A')}")
    print(f"HTML report: {report_path}")
    print("Trace:")
    for item in state.get("trace", []):
        print(f"- {item}")


if __name__ == "__main__":
    main()
