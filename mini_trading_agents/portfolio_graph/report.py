from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from mini_trading_agents.reporting.report_theme import STYLE


def make_portfolio_report_path(report_dir: str, run_id: str) -> Path:
    Path(report_dir).mkdir(parents=True, exist_ok=True)
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in run_id)
    return Path(report_dir) / f"{safe}.html"


def write_portfolio_html_report(path: str | Path, state: dict[str, Any]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_portfolio_html_report(state), encoding="utf-8")
    return path


def render_portfolio_html_report(state: dict[str, Any]) -> str:
    plan = state.get("portfolio_plan") or {}
    validation = state.get("validation_result") or state.get("preflight_result") or {}
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Portfolio Report - {_e(state.get("run_id", "portfolio"))}</title>
  <style>{STYLE}</style>
</head>
<body>
<main class="page">
  <section class="market-shell" id="overview">
    <div class="quote-header">
      <div>
        <div class="symbol-line">Global Portfolio Graph / {_e(state.get("analysis_date", ""))}</div>
        <h1 class="quote-title">Portfolio Decision</h1>
        <div class="quote-row">
          <div class="price">{_e(plan.get("decision", state.get("rejected_plan", {}).get("status", "PENDING")))}</div>
        </div>
        <p class="market-note">{_e(plan.get("portfolio_rationale", state.get("rejected_plan", {}).get("reason", "")))}</p>
      </div>
      <div class="decision-card">
        <div class="label">Run ID</div>
        <div>{_e(state.get("run_id", ""))}</div>
        <div class="label">Tickers</div>
        <div>{_e(", ".join(state.get("tickers", [])))}</div>
        <div class="label">Validation</div>
        <div>{_e(validation.get("status", "N/A"))}</div>
      </div>
    </div>
    <nav class="subnav">
      <a class="active" href="#overview">Overview</a>
      <a href="#weights">Weights</a>
      <a href="#cross-section">Cross Section</a>
      <a href="#ticker-advice">Ticker Advice</a>
      <a href="#risk">Risk</a>
      <a href="#orders">Orders</a>
      <a href="#paper-execution">Paper Execution</a>
      <a href="#node-drilldown">Node Drilldown</a>
    </nav>
  </section>
  {_weights_section(plan)}
  {_cross_section_section(state)}
  {_ticker_advice_section(state)}
  {_risk_section(state)}
  {_orders_section(state)}
  {_paper_execution_section(state)}
  {_node_drilldown_section(state)}
</main>
</body>
</html>"""


def _weights_section(plan: dict[str, Any]) -> str:
    weights = plan.get("target_weights") or {}
    rows = "".join(
        f"<div class='data-row'><span>{_e(ticker)}</span><strong>{float(weight):.1%}</strong></div>"
        for ticker, weight in sorted(weights.items())
    )
    return f"<section class='section' id='weights'><h2>Target Weights</h2><div class='panel data-table'>{rows}</div></section>"


def _ticker_advice_section(state: dict[str, Any]) -> str:
    advices = state.get("trade_advices") or {}
    cards = []
    for ticker, advice in advices.items():
        cards.append(
            f"""<div class="panel">
  <h3>{_e(ticker)}</h3>
  <div class="data-row"><span>Action</span><strong>{_e(advice.get("action", ""))}</strong></div>
  <div class="data-row"><span>Intent</span><strong>{_e(advice.get("trade_intent", ""))}</strong></div>
  <div class="data-row"><span>Conviction</span><strong>{_e(advice.get("position_size", ""))}</strong></div>
  <div class="data-row"><span>Confidence</span><strong>{float(advice.get("confidence", 0)):.1%}</strong></div>
  <div class="data-row"><span>{_e(_period_label("Expected Return", advice))}</span><strong>{float(advice.get("expected_return_pct", 0)):.1%}</strong></div>
  <p class="summary">{_e(advice.get("rationale", ""))}</p>
</div>"""
        )
    return f"<section class='section' id='ticker-advice'><h2>Ticker Advice</h2><div class='grid grid-3'>{''.join(cards)}</div></section>"


def _cross_section_section(state: dict[str, Any]) -> str:
    cross = state.get("cross_section") or state.get("portfolio_context", {}).get("cross_section", {})
    action_rows = "".join(
        f"<div class='data-row'><span>{_e(action)}</span><strong>{count}</strong></div>"
        for action, count in (cross.get("action_distribution") or {}).items()
    )
    ranked_rows = "".join(
        f"<div class='data-row'><span>{index}. {_e(ticker)}</span><strong>{_e(_advice_label(state, ticker))}</strong></div>"
        for index, ticker in enumerate(cross.get("ranked_candidates", []), start=1)
    )
    failed_rows = "".join(
        f"<div class='data-row'><span>{_e(item.get('ticker', ''))}</span><strong>{_e(item.get('error', ''))}</strong></div>"
        for item in cross.get("failed_tickers", [])
    )
    if not failed_rows:
        failed_rows = "<div class='data-row'><span>Failed Tickers</span><strong>None</strong></div>"
    return f"""<section class="section" id="cross-section">
  <h2>Cross Section</h2>
  <div class="grid grid-3">
    <div class="panel"><h3>Action Distribution</h3><div class="data-table">{action_rows}</div></div>
    <div class="panel"><h3>Opportunity Ranking</h3><div class="data-table">{ranked_rows}</div></div>
    <div class="panel"><h3>Failures</h3><div class="data-table">{failed_rows}</div></div>
  </div>
</section>"""


def _risk_section(state: dict[str, Any]) -> str:
    risk = state.get("portfolio_risk_review") or {}
    validation = state.get("validation_result") or state.get("preflight_result") or {}
    execution_validation = state.get("execution_validation_result") or {}
    validation_items = _validation_items(validation)
    execution_items = _validation_items(execution_validation)
    controls = "".join(f"<li>{_e(item)}</li>" for item in (state.get("portfolio_plan") or {}).get("risk_controls", []))
    concentration = "".join(f"<li>{_e(item)}</li>" for item in risk.get("concentration_notes", []))
    return f"""<section class="section" id="risk">
  <h2>Risk Review</h2>
  <div class="grid grid-2">
    <div class="panel"><h3>Risk Summary</h3><p class="summary">{_e(risk.get("risk_summary", ""))}</p><ul>{concentration}{controls}</ul></div>
    <div class="panel"><h3>Portfolio Validation</h3><p class="summary">Status: {_e(validation.get("status", "N/A"))}</p><div class="data-table">{validation_items}</div></div>
    <div class="panel"><h3>Execution Validation</h3><p class="summary">Status: {_e(execution_validation.get("status", "N/A"))}</p><div class="data-table">{execution_items}</div></div>
  </div>
</section>"""


def _orders_section(state: dict[str, Any]) -> str:
    execution = state.get("execution_plan") or {}
    rows = "".join(
        f"<div class='data-row'><span>{_e(order.get('ticker', ''))} {_e(order.get('side', ''))}</span><strong>{float(order.get('target_weight', 0)):.1%} / ${float(order.get('estimated_delta_value', 0)):,.0f}</strong></div>"
        for order in execution.get("orders", [])
    )
    return f"<section class='section' id='orders'><h2>Execution Plan</h2><div class='panel data-table'>{rows}</div></section>"


def _paper_execution_section(state: dict[str, Any]) -> str:
    result = state.get("paper_trading_result")
    if not result:
        return ""
    rows = "".join(
        f"<div class='data-row'><span>{_e(order.get('ticker', ''))} {_e(order.get('status', ''))}</span><strong>{_e(order.get('order_id', 'N/A'))}</strong></div>"
        for order in result.get("orders", [])
    )
    if not rows:
        rows = "<div class='data-row'><span>Orders</span><strong>None</strong></div>"
    return f"""<section class="section" id="paper-execution">
  <h2>Paper Execution</h2>
  <div class="grid grid-2">
    <div class="panel data-table">
      <div class="data-row"><span>Provider</span><strong>{_e(result.get("provider", "N/A"))}</strong></div>
      <div class="data-row"><span>Status</span><strong>{_e(result.get("status", "N/A"))}</strong></div>
      <div class="data-row"><span>Account</span><strong>{_e(result.get("account_id", "N/A"))}</strong></div>
      <div class="data-row"><span>Equity</span><strong>{_e(result.get("equity", "N/A"))}</strong></div>
    </div>
    <div class="panel data-table">{rows}</div>
  </div>
</section>"""


def _node_drilldown_section(state: dict[str, Any]) -> str:
    cards = []
    for result in state.get("ticker_results", []):
        final_state = result.get("final_state", {})
        decision = final_state.get("final_trade_decision", {})
        cards.append(
            f"""<div class="panel">
  <h3>{_e(result.get("ticker", ""))}</h3>
  <div class="data-row"><span>Status</span><strong>{_e(result.get("status", ""))}</strong></div>
  <div class="data-row"><span>Decision</span><strong>{_e(decision.get("action", "N/A"))}</strong></div>
  <div class="data-row"><span>Trace Steps</span><strong>{len(final_state.get("trace", []))}</strong></div>
  <p class="summary">{_e(decision.get("reason", result.get("error", "")))}</p>
</div>"""
        )
    return f"<section class='section' id='node-drilldown'><h2>Single-Ticker Node Drilldown</h2><div class='grid grid-3'>{''.join(cards)}</div></section>"


def _period_label(label: str, advice: dict[str, Any]) -> str:
    days = advice.get("expected_holding_days")
    return f"{label} ({days}d, not annualized)" if days else f"{label} (not annualized)"


def _validation_items(validation: dict[str, Any]) -> str:
    if not validation:
        return "<div class='data-row'><span>Validation</span><strong>N/A</strong></div>"
    violations = validation.get("violations", [])
    if violations:
        return "".join(
            f"<div class='data-row'><span>{_e(item.get('type', 'Violation'))}</span><strong>{_e(item.get('message', ''))}</strong></div>"
            for item in violations
        )
    checks = validation.get("checks", [])
    if not checks:
        return "<div class='data-row'><span>Plan Feasibility</span><strong>Pass</strong></div>"
    return "".join(
        f"<div class='data-row'><span>{_e(item.get('name', 'Check'))}</span><strong>{_check_value(item)}</strong></div>"
        for item in checks
    )


def _check_value(item: dict[str, Any]) -> str:
    status = "Pass" if item.get("passed") else "Fail"
    if "current" not in item:
        return status
    current = float(item["current"])
    limit = float(item.get("limit", 0))
    if abs(current) > 1 or abs(limit) > 1:
        return f"{status} ({current:g} / {limit:g})"
    return f"{status} ({current:.1%} / {limit:.1%})"


def _e(value: Any) -> str:
    return escape(str(value))


def _advice_label(state: dict[str, Any], ticker: str) -> str:
    advice = (state.get("trade_advices") or {}).get(ticker, {})
    return f"{advice.get('action', 'N/A')} {float(advice.get('confidence', 0)):.1%}"
