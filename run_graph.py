from __future__ import annotations

import argparse
from contextlib import ExitStack, nullcontext
from pathlib import Path
from uuid import uuid4

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.store.sqlite import SqliteStore as LangGraphSqliteStore

from mini_trading_agents.config import load_config
from mini_trading_agents.execution import build_execution_adapter
from mini_trading_agents.llm_adapter import get_llm_adapter
from mini_trading_agents.portfolio_graph import build_portfolio_workflow, initial_portfolio_state
from mini_trading_agents.portfolio_graph.report import make_portfolio_report_path, write_portfolio_html_report
from mini_trading_agents.storage import BusinessStore, SnapshotStore, build_portfolio_memory_event


DEFAULT_CONFIG = "config.toml"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run graph-mode multi-ticker trading analysis.")
    parser.add_argument("--config", default=DEFAULT_CONFIG, help="TOML config file.")
    parser.add_argument("--tickers", help="Comma-separated ticker list. Defaults to [run].tickers.")
    parser.add_argument("--date", help="Analysis date. Empty string uses [run].analysis_date.")
    parser.add_argument("--run-id", help="Stable graph run id. Generated when omitted.")
    parser.add_argument("--data-provider", choices=["sample", "yahoo"], help="Shortcut provider. Defaults to [data_providers].default.")
    parser.add_argument("--market-provider", choices=["sample", "yahoo", "alpaca"], help="Provider for market data.")
    parser.add_argument("--report-dir", help="Directory for HTML reports. Defaults to [reporting].report_dir.")
    args = parser.parse_args()

    app_config = load_config(args.config)
    persistence = app_config.persistence
    run_config = app_config.run
    reporting = app_config.reporting

    _run_llm_runtime_check(app_config.llm.__dict__)

    tickers = _resolve_tickers(args.tickers, run_config.tickers)
    analysis_date = _resolve_cli_date(args.date, run_config.analysis_date)
    snapshot_store = SnapshotStore(persistence.snapshot_path) if persistence.snapshot_enabled else None
    business_store = (
        BusinessStore(persistence.storage_path)
        if persistence.decision_memory_enabled or app_config.paper_trading.enable
        else None
    )
    report_dir = args.report_dir or reporting.report_dir
    run_id = args.run_id or f"GRAPH-{analysis_date}-{uuid4().hex[:8]}"

    state = initial_portfolio_state(
        run_id=run_id,
        tickers=tickers,
        analysis_date=analysis_date,
        data_providers=_resolve_data_providers(app_config, args),
        data_provider_config=_data_provider_config(),
        app_config=app_config,
    )
    if snapshot_store:
        snapshot_store.create_or_update_run(run_id, state)
    if business_store and persistence.decision_memory_enabled:
        business_store.create_or_update_run(run_id, state)

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
                if snapshot_store:
                    snapshot_store.save_snapshot(run_id, step_index, final_state)
                step_index += 1
        if persistence.decision_memory_enabled:
            _save_portfolio_store_memory(memory_store, run_id, final_state)

    if snapshot_store:
        snapshot_store.mark_completed(run_id, final_state)
    if business_store and persistence.decision_memory_enabled:
        business_store.mark_completed(run_id, final_state)
        business_store.save_portfolio_memory(run_id, final_state)

    if app_config.paper_trading.enable:
        if final_state.get("rejected_plan"):
            raise SystemExit("Paper execution skipped because the graph plan was rejected.")
        if not (final_state.get("validation_result") or {}).get("valid"):
            raise SystemExit("Paper execution skipped because graph validation is not valid.")
        if not (final_state.get("execution_validation_result") or {}).get("valid"):
            raise SystemExit("Paper execution skipped because execution validation is not valid.")
        paper_adapter = build_execution_adapter(app_config.paper_trading)
        final_state["paper_trading_result"] = paper_adapter.apply_portfolio_plan(run_id, final_state)
        if business_store:
            business_store.mark_completed(run_id, final_state)
            business_store.save_trade_outcomes_from_paper_execution(run_id, final_state)

    report_path = make_portfolio_report_path(report_dir, run_id)
    write_portfolio_html_report(report_path, final_state)

    _print_state(
        final_state,
        report_path,
        persistence.snapshot_path if snapshot_store else None,
        persistence.storage_path if business_store else None,
    )


def _run_llm_runtime_check(llm_config: dict) -> None:
    try:
        get_llm_adapter(llm_config).check_connection()
    except Exception as exc:
        raise SystemExit(
            "LLM runtime check failed before graph execution: "
            f"{type(exc).__name__}: {str(exc)[:500]}"
        ) from exc


def _resolve_tickers(cli_tickers: str | None, config_tickers: tuple[str, ...]) -> list[str]:
    if cli_tickers:
        tickers = cli_tickers.split(",")
    else:
        tickers = list(config_tickers)
    return [ticker.strip().upper() for ticker in tickers if ticker.strip()]


def _resolve_cli_date(cli_date: str | None, config_date: str) -> str:
    if cli_date is None:
        return config_date
    return cli_date.strip() or config_date


def _resolve_data_providers(app_config, args) -> dict:
    provider_config = app_config.data_providers
    default_provider = args.data_provider or provider_config.default
    return {
        "market": args.market_provider or provider_config.market or default_provider,
        "sentiment": provider_config.sentiment or default_provider,
        "news": provider_config.news or default_provider,
        "fundamentals": provider_config.fundamentals or default_provider,
    }


def _data_provider_config() -> dict:
    return {"market": {"base_url": "https://data.alpaca.markets", "feed": "iex"}}


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


def _print_state(state: dict, report_path, snapshot_path: str | None, storage_path: str | None) -> None:
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
    print(f"Snapshot: {snapshot_path or 'disabled'}")
    print(f"Storage: {storage_path or 'disabled'}")
    print(f"HTML report: {report_path}")
    print("Trace:")
    for item in state.get("trace", []):
        print(f"- {item}")


if __name__ == "__main__":
    main()
