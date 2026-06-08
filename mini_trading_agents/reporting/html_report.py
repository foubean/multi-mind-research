from __future__ import annotations

from datetime import UTC, datetime
from html import escape
from pathlib import Path
from typing import Any

from mini_trading_agents.reporting.report_theme import PHASES, SIGNAL_LABELS, STYLE


def make_report_path(report_dir: str, ticker: str, analysis_date: str) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    directory = Path(report_dir)
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{ticker.upper()}_{analysis_date}_{timestamp}.html"


def write_html_report(path: str | Path, state: dict[str, Any], run_id: str) -> Path:
    report_path = Path(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_html_report(state, run_id), encoding="utf-8")
    return report_path


def render_html_report(state: dict[str, Any], run_id: str) -> str:
    ticker = state["ticker"]
    date = state["analysis_date"]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_e(ticker)} Trading Agent Report</title>
  <style>{STYLE}</style>
</head>
<body>
  <main class="page">
    <section class="market-shell" id="overview">
      {_quote_header(state, run_id, date)}
      <nav class="subnav" aria-label="Report sections">
        <a class="active" href="#overview">Overview</a>
        <a href="#key-data">Key Data</a>
        <a href="#agent-workflow">Agent Workflow</a>
        <a href="#trade-advice">Trade Advice</a>
        <a href="#data-lineage">Data Lineage</a>
        {_paper_nav(state)}
        <a href="#llm-trace">LLM Trace</a>
      </nav>
      {_key_data_section(state)}
    </section>

    {_decision_rationale(state)}
    {_trade_advice_section(state)}
    {_workflow_explorer_section(state)}
    {_data_dashboard_section(state)}
    {_data_lineage_section(state)}
    {_paper_trading_section(state)}
    {_llm_section(state)}
  </main>
  <a class="back-top" href="#overview" aria-label="Back to top" title="Back to top">^</a>
  <script>{_interaction_script()}</script>
</body>
</html>"""


def _quote_header(state: dict[str, Any], run_id: str, date: str) -> str:
    ticker = state["ticker"]
    market = state.get("market_data", {})
    decision = state.get("final_trade_decision", {})
    action = decision.get("action", "N/A")
    change = _safe_float(market.get("change_pct"))
    change_class = "positive" if change >= 0 else "negative"
    data_status = state.get("data_status", {})
    providers = data_status.get("providers", {})
    provider_text = ", ".join(f"{key}: {value}" for key, value in providers.items()) or "N/A"
    return f"""
      <header class="quote-header">
        <div>
          <div class="symbol-line">{_e(ticker)} | Analysis date {_e(date)} | Run {_e(run_id)}</div>
          <h1 class="quote-title">{_e(ticker)} Multi-Agent Trading Report</h1>
          <div class="quote-row">
            <div class="price">{_e(_fmt(market.get("close")))}</div>
            <div class="change {change_class}">{_pct_value(market.get("change_pct"))}</div>
          </div>
          <div class="market-note">Data status: {_e(data_status.get("status", "N/A"))} | Providers: {_e(provider_text)}</div>
        </div>
        <aside class="decision-card">
          <div class="label">Final Decision</div>
          <div class="action {_e(action)}">{_e(action)}</div>
          <div><strong>Position:</strong> {_e(decision.get("position_size", "N/A"))}</div>
          <div><strong>Confidence:</strong> {_pct(decision.get("confidence"))}</div>
          <div class="summary">{_e(_first_sentence(decision.get("reason", "No final decision available.")))}</div>
        </aside>
      </header>
"""


def _paper_nav(state: dict[str, Any]) -> str:
    if not state.get("paper_trading_result"):
        return ""
    return '<a href="#paper-trading">Paper Trading</a>'


def _key_data_section(state: dict[str, Any]) -> str:
    market = state.get("market_data", {})
    fundamentals = state.get("fundamentals_data", {})
    sentiment = state.get("sentiment_data", {})
    volume_ratio = _ratio(market.get("volume"), market.get("average_volume_20d"))
    ma20_gap = _gap_pct(market.get("close"), market.get("moving_average_20"))
    ma60_gap = _gap_pct(market.get("close"), market.get("moving_average_60"))
    sentiment_total = sum(_safe_float(sentiment.get(key)) for key in ("positive_mentions", "negative_mentions", "neutral_mentions"))
    positive_share = _safe_float(sentiment.get("positive_mentions")) / sentiment_total if sentiment_total else 0
    return f"""
      <section class="quote-grid" id="key-data">
        <div class="panel">
          <h2>Key Data</h2>
          <div class="data-table">
            {_data_row("Close", _fmt(market.get("close")))}
            {_data_row("Change", _pct_value(market.get("change_pct")))}
            {_data_row("Volume", _compact_number(market.get("volume")))}
            {_data_row("20D Avg Volume", _compact_number(market.get("average_volume_20d")))}
            {_data_row("Volume / 20D Avg", _fmt(volume_ratio))}
            {_data_row("Forward P/E", _fmt(fundamentals.get("forward_pe")))}
          </div>
        </div>
        <div class="panel range-card">
          <h2>Technical Position</h2>
          {_range_bar("Price vs MA20", ma20_gap, -10, 10)}
          {_range_bar("Price vs MA60", ma60_gap, -20, 20)}
          {_range_bar("RSI 14", market.get("rsi_14"), 0, 100)}
          {_range_bar("Positive Sentiment Share", positive_share, 0, 1)}
          <div class="source-note">Range bars use current normalized fields, not external Investing.com proprietary values.</div>
        </div>
      </section>
"""


def _decision_rationale(state: dict[str, Any]) -> str:
    decision = state.get("final_trade_decision", {})
    trader = state.get("trader_investment_plan", {})
    risk = state.get("risk_assessment", {})
    return f"""
    <section class="section grid grid-3" id="risk-review">
      <div class="panel">
        <h2>Decision Rationale</h2>
        <p>{_e(decision.get("reason", "No final decision available."))}</p>
      </div>
      <div class="panel">
        <h2>Trader Proposal</h2>
        <p><span class="tag">{_e(trader.get("action", "N/A"))}</span></p>
        <p class="summary">{_e(trader.get("rationale", ""))}</p>
      </div>
      <div class="panel">
        <h2>Risk Review</h2>
        <p><span class="tag">{_e(risk.get("status", "N/A"))}</span></p>
        <p class="summary">{_e(" ".join(risk.get("notes", [])[-3:]))}</p>
      </div>
    </section>
"""


def _trade_advice_section(state: dict[str, Any]) -> str:
    advice = state.get("trade_advice") or state.get("trader_investment_plan")
    if not advice:
        return ""
    invalidations = "".join(f"<li>{_e(item)}</li>" for item in advice.get("invalidation_conditions", []))
    return f"""
    <section class="section" id="trade-advice">
      <h2>Trade Advice</h2>
      <div class="grid grid-4">
        {_metric_panel("Preference", [
            ("Risk Profile", advice.get("risk_profile")),
            ("Trading Style", advice.get("trading_style")),
            ("Holding Days", advice.get("expected_holding_days")),
            ("Conviction", advice.get("position_size")),
        ])}
        {_metric_panel("Expectation", [
            ("Action", advice.get("action")),
            ("Intent", advice.get("trade_intent", "N/A")),
            ("Confidence", _pct(advice.get("confidence"))),
            ("Expected Return", _pct(advice.get("expected_return_pct"))),
            ("Expected Risk", _pct(advice.get("expected_risk_pct"))),
        ])}
        {_plan_card("Entry", advice.get("entry_plan", {}))}
        {_plan_card("Add", advice.get("add_position_plan", {}))}
      </div>
      <div class="grid grid-3" style="margin-top:16px">
        {_plan_card("Reduce", advice.get("reduce_position_plan", {}))}
        {_plan_card("Stop Loss", advice.get("stop_loss_plan", {}))}
        <div class="panel">
          <h3>Invalidation Conditions</h3>
          <ul class="summary">{invalidations}</ul>
        </div>
      </div>
      <div class="panel" style="margin-top:16px"><p>{_e(advice.get("rationale", ""))}</p></div>
    </section>
"""


def _plan_card(title: str, plan: dict[str, Any]) -> str:
    return _metric_panel(
        title,
        [
            ("Method", plan.get("method", "N/A")),
            ("Fraction", _pct(plan.get("fraction"))),
            ("Trigger", plan.get("trigger", "N/A")),
        ],
    )


def _workflow_explorer_section(state: dict[str, Any]) -> str:
    summaries = {
        "Data": _data_summary(state),
        "Analysts": _analyst_summary(state),
        "Research": _research_summary(state),
        "Plan": _plan_summary(state),
        "Risk": _risk_summary(state),
        "Decision": _decision_summary(state),
    }
    details = _phase_details(state)
    steps = "\n".join(
        f"""
        <button class="step {'active' if index == 0 else ''}" type="button" data-phase="{_e(_phase_key(name))}">
          <strong>{_e(name)}</strong>
          <small>{_e(nodes)}</small>
        </button>
        """
        for index, (name, nodes, _fallback) in enumerate(PHASES)
    )
    cards = "\n".join(
        f"""
        <article class="stage {'active' if index == 0 else ''}" data-phase-card="{_e(_phase_key(name))}">
          <h3>{_e(name)}</h3>
          <div class="nodes">{_e(nodes)}</div>
          <p class="summary">{_e(summaries.get(name, fallback))}</p>
          <div class="stage-detail">{details.get(name, "")}</div>
        </article>
        """
        for index, (name, nodes, fallback) in enumerate(PHASES)
    )
    return f"""
    <section class="section" id="agent-workflow">
      <h2>Agent Workflow Explorer</h2>
      <div class="workflow-explorer">
        <div class="panel">
          <div class="workflow">{steps}</div>
          <div class="svg-wrap">{_workflow_svg()}</div>
        </div>
        <div class="stage-stack">{cards}</div>
      </div>
    </section>
"""


def _data_dashboard_section(state: dict[str, Any]) -> str:
    return f"""
    <section class="section">
      <h2>Target Data Dashboard</h2>
      <div class="grid grid-4">
        {_market_metrics(state.get("market_data", {}))}
        {_sentiment_metrics(state.get("sentiment_data", {}))}
        {_news_metrics(state.get("news_data", {}))}
        {_fundamental_metrics(state.get("fundamentals_data", {}))}
      </div>
    </section>
"""


def _data_lineage_section(state: dict[str, Any]) -> str:
    cards = "\n".join(
        [
            _lineage_card("Market", state.get("market_data", {})),
            _lineage_card("Sentiment", state.get("sentiment_data", {})),
            _lineage_card("News", state.get("news_data", {})),
            _lineage_card("Fundamentals", state.get("fundamentals_data", {})),
        ]
    )
    return f"""
    <section class="section" id="data-lineage">
      <h2>Data Lineage</h2>
      <div class="lineage-grid">{cards}</div>
    </section>
"""


def _paper_trading_section(state: dict[str, Any]) -> str:
    result = state.get("paper_trading_result")
    if not result:
        return ""
    return f"""
    <section class="section" id="paper-trading">
      <h2>Paper Trading</h2>
      <div class="grid grid-4">
        {_metric_panel("Account", [
            ("Status", result.get("status")),
            ("Account", result.get("account_id")),
            ("Provider", result.get("provider", "local")),
            ("Equity", result.get("equity")),
            ("Cash", result.get("cash")),
        ])}
        {_metric_panel("Order", [
            ("Action", result.get("action")),
            ("Target Weight", _pct(result.get("target_weight"))),
            ("Quantity Delta", result.get("quantity_delta")),
            ("Fill Price", result.get("fill_price")),
        ])}
        {_metric_panel("Position", [
            ("Ticker", result.get("ticker")),
            ("Quantity", result.get("position_quantity")),
            ("Average Cost", result.get("average_cost")),
            ("Market Value", result.get("market_value")),
        ])}
        {_metric_panel("PnL", [
            ("Unrealized", result.get("unrealized_pnl")),
            ("Realized", result.get("realized_pnl")),
            ("Fee", result.get("fee")),
            ("History Points", result.get("portfolio_history_points", "N/A")),
        ])}
      </div>
      <div class="panel" style="margin-top:16px"><p class="summary">{_e(result.get("message", ""))}</p></div>
    </section>
"""


def _lineage_card(title: str, data: dict[str, Any]) -> str:
    lineage = data.get("lineage", {})
    transforms = lineage.get("transforms", [])
    transform_items = "".join(_lineage_transform(item) for item in transforms[:5])
    if len(transforms) > 5:
        transform_items += f'<div class="summary">+ {len(transforms) - 5} more transforms</div>'
    return f"""
      <article class="panel lineage-card">
        <h3>{_e(title)}</h3>
        <div class="data-table">
          {_data_row("Provider", lineage.get("provider", data.get("source", "N/A")))}
          {_data_row("Adapter", lineage.get("adapter", "N/A"))}
          {_data_row("Raw Source", lineage.get("raw_source", "N/A"))}
          {_data_row("Raw Ref", lineage.get("raw_ref", "N/A"))}
          {_data_row("Fetched At", _short_time(lineage.get("fetched_at")))}
          {_data_row("Used By", lineage.get("used_by", data.get("used_by", "N/A")))}
        </div>
        <div class="lineage-transforms">{transform_items or '<p class="summary">No transform metadata recorded.</p>'}</div>
      </article>
"""


def _lineage_transform(item: dict[str, Any]) -> str:
    derived_from = ", ".join(str(value) for value in item.get("derived_from", []))
    return f"""
      <div class="lineage-transform">
        <strong>{_e(item.get("field", "unknown_field"))}</strong>
        <span>{_e(item.get("method", "unknown method"))} | from {_e(derived_from or "N/A")}</span>
      </div>
"""


def _phase_details(state: dict[str, Any]) -> dict[str, str]:
    return {
        "Data": _data_phase_detail(state),
        "Analysts": _analyst_phase_detail(state),
        "Research": _research_phase_detail(state),
        "Plan": _plan_phase_detail(state),
        "Risk": _risk_phase_detail(state),
        "Decision": _decision_phase_detail(state),
    }


def _data_phase_detail(state: dict[str, Any]) -> str:
    status = state.get("data_status", {})
    providers = status.get("providers", {})
    rows = "".join(_data_row(key.title(), value) for key, value in providers.items())
    return f"""
      <div class="data-table">
        {_data_row("Status", status.get("status", "N/A"))}
        {rows}
      </div>
    """


def _analyst_phase_detail(state: dict[str, Any]) -> str:
    reports = [
        ("Market", state.get("market_report")),
        ("Sentiment", state.get("sentiment_report")),
        ("News", state.get("news_report")),
        ("Fundamentals", state.get("fundamentals_report")),
    ]
    return '<div class="stage-metrics">' + "".join(
        _mini_report_card(name, report) for name, report in reports if report
    ) + "</div>"


def _research_phase_detail(state: dict[str, Any]) -> str:
    plan = state.get("investment_plan", {})
    debate = state.get("investment_debate_state", {})
    return f"""
      <div class="data-table">
        {_data_row("Manager Stance", plan.get("stance", "N/A"))}
        {_data_row("Debate Turns", debate.get("count", 0))}
      </div>
      <p class="summary">{_e(plan.get("summary", ""))}</p>
      {_debate_turns("Investment Debate Loop", debate, "bull_researcher", "bear_researcher")}
    """


def _plan_phase_detail(state: dict[str, Any]) -> str:
    trader = state.get("trader_investment_plan", {})
    return f"""
      <div class="data-table">
        {_data_row("Action", trader.get("action", "N/A"))}
        {_data_row("Position Size", trader.get("position_size", "N/A"))}
      </div>
      <p class="summary">{_e(trader.get("rationale", ""))}</p>
    """


def _risk_phase_detail(state: dict[str, Any]) -> str:
    risk = state.get("risk_assessment", {})
    debate = state.get("risk_debate_state", {})
    notes = " ".join(risk.get("notes", [])[-3:])
    return f"""
      <div class="data-table">
        {_data_row("Status", risk.get("status", "N/A"))}
        {_data_row("Risk Turns", debate.get("count", 0))}
      </div>
      <p class="summary">{_e(notes)}</p>
      {_debate_turns("Risk Debate Loop", debate, "aggressive", "conservative")}
    """


def _decision_phase_detail(state: dict[str, Any]) -> str:
    decision = state.get("final_trade_decision", {})
    return f"""
      <div class="data-table">
        {_data_row("Action", decision.get("action", "N/A"))}
        {_data_row("Confidence", _pct(decision.get("confidence")))}
        {_data_row("Position Size", decision.get("position_size", "N/A"))}
      </div>
      <p class="summary">{_e(decision.get("reason", ""))}</p>
    """


def _mini_report_card(name: str, report: dict[str, Any]) -> str:
    signal = report.get("signal", "neutral")
    return (
        f'<div class="metric"><div class="label">{_e(name)}</div>'
        f'<div class="value {_e(signal)}">{_e(SIGNAL_LABELS.get(signal, signal))}</div>'
        f'<div class="summary">{_e(_first_sentence(report.get("summary", "")))}</div></div>'
    )


def _debate_turns(title: str, debate: dict[str, Any], first: str, second: str) -> str:
    history = debate.get("history", [])
    if not history:
        return ""
    items = []
    for index, text in enumerate(history, start=1):
        klass = "bear" if index % 2 == 0 else ""
        items.append(f'<div class="debate-item {klass}"><strong>Turn {index}</strong><p>{_e(text)}</p></div>')
    return f"""
      <div>
        <h3>{_e(title)}</h3>
        <p class="summary">Loop: {_e(first)} -> {_e(second)} -> route or continue. Total turns: {_e(str(debate.get("count", len(history))))}</p>
        <div class="debate-list">{''.join(items)}</div>
      </div>
"""


def _llm_section(state: dict[str, Any]) -> str:
    traces = state.get("llm_usage_trace", [])
    if not traces:
        return """
    <section class="section" id="llm-trace">
      <h2>LLM Usage</h2>
      <div class="panel"><p class="summary">No LLM usage trace was recorded for this run.</p></div>
    </section>
"""
    items = "\n".join(
        f'<div class="metric"><div class="label">{_e(item.get("node", ""))}</div>'
        f'<div class="value">{_e(item.get("status", ""))}</div>'
        f'<div class="summary">{_e(item.get("model", ""))}</div></div>'
        for item in traces
    )
    return f"""
    <section class="section" id="llm-trace">
      <h2>LLM Usage</h2>
      <div class="grid grid-4">{items}</div>
    </section>
"""


def _market_metrics(data: dict[str, Any]) -> str:
    return _metric_panel(
        "Market",
        [
            ("Close", data.get("close")),
            ("Change", _pct_value(data.get("change_pct"))),
            ("RSI 14", data.get("rsi_14")),
            ("Volatility", _pct(data.get("volatility_20d"))),
        ],
    )


def _sentiment_metrics(data: dict[str, Any]) -> str:
    total = sum(_safe_float(data.get(key)) for key in ("positive_mentions", "negative_mentions", "neutral_mentions"))
    rows = [
        ("Positive", data.get("positive_mentions")),
        ("Negative", data.get("negative_mentions")),
        ("Neutral", data.get("neutral_mentions")),
    ]
    bars = "".join(_bar_row(label, value, total) for label, value in rows)
    topics = ", ".join(data.get("top_topics", [])[:3])
    return f'<div class="panel"><h3>Sentiment</h3>{bars}<p class="summary">Score: {_e(str(data.get("sentiment_score", "N/A")))} | Topics: {_e(topics)}</p></div>'


def _news_metrics(data: dict[str, Any]) -> str:
    items = data.get("items", [])
    sentiments = [item.get("sentiment") for item in items]
    return _metric_panel(
        "News",
        [
            ("Items", len(items)),
            ("Positive", sentiments.count("positive")),
            ("Neutral", sentiments.count("neutral")),
            ("Negative", sentiments.count("negative")),
        ],
    )


def _fundamental_metrics(data: dict[str, Any]) -> str:
    return _metric_panel(
        "Fundamentals",
        [
            ("Revenue Growth", _pct(data.get("revenue_growth_yoy"))),
            ("Operating Margin", _pct(data.get("operating_margin"))),
            ("Forward P/E", data.get("forward_pe")),
            ("Debt/Equity", data.get("debt_to_equity")),
        ],
    )


def _metric_panel(title: str, rows: list[tuple[str, Any]]) -> str:
    metrics = "".join(
        f'<div class="metric"><div class="label">{_e(label)}</div><div class="value">{_e(str(_fmt(value)))}</div></div>'
        for label, value in rows
    )
    return f'<div class="panel"><h3>{_e(title)}</h3><div class="grid grid-2">{metrics}</div></div>'


def _data_summary(state: dict[str, Any]) -> str:
    status = state.get("data_status", {})
    providers = status.get("providers", {})
    provider_text = ", ".join(f"{key}={value}" for key, value in providers.items())
    return f"{status.get('status', 'N/A')} data coverage. Providers: {provider_text or 'N/A'}."


def _analyst_summary(state: dict[str, Any]) -> str:
    reports = [
        state.get("market_report"),
        state.get("sentiment_report"),
        state.get("news_report"),
        state.get("fundamentals_report"),
    ]
    signals = [report.get("signal", "neutral") for report in reports if report]
    if not signals:
        return "No analyst reports available."
    bullish = signals.count("bullish")
    bearish = signals.count("bearish")
    neutral = signals.count("neutral")
    return f"Signals: bullish={bullish}, neutral={neutral}, bearish={bearish}."


def _research_summary(state: dict[str, Any]) -> str:
    debate = state.get("investment_debate_state", {})
    plan = state.get("investment_plan", {})
    return f"{debate.get('count', 0)} research turns. Manager stance: {plan.get('stance', 'N/A')}."


def _plan_summary(state: dict[str, Any]) -> str:
    trader = state.get("trader_investment_plan", {})
    return f"Trader proposed {trader.get('action', 'N/A')} with {trader.get('position_size', 'N/A')} position size."


def _risk_summary(state: dict[str, Any]) -> str:
    debate = state.get("risk_debate_state", {})
    risk = state.get("risk_assessment", {})
    return f"{debate.get('count', 0)} risk turns. Assessment status: {risk.get('status', 'N/A')}."


def _decision_summary(state: dict[str, Any]) -> str:
    decision = state.get("final_trade_decision", {})
    return f"Final action: {decision.get('action', 'N/A')}; confidence: {_pct(decision.get('confidence'))}."


def _data_row(label: str, value: Any) -> str:
    return f'<div class="data-row"><span>{_e(label)}</span><strong>{_e(str(value))}</strong></div>'


def _phase_key(name: str) -> str:
    return name.lower().replace(" ", "-")


def _range_bar(label: str, value: Any, low: float, high: float) -> str:
    numeric = _safe_float(value)
    if high <= low:
        width = 0
    else:
        width = int(max(0, min(1, (numeric - low) / (high - low))) * 100)
    return (
        f'<div><div class="range-label"><span>{_e(label)}</span><strong>{_e(_fmt(numeric))}</strong></div>'
        f'<div class="range-track"><span style="width:{width}%"></span></div></div>'
    )


def _bar_row(label: str, value: Any, total: float) -> str:
    numeric = _safe_float(value)
    width = 0 if total <= 0 else int(numeric / total * 100)
    return (
        f'<div class="chart-row"><div class="chart-label">{_e(label)}</div>'
        f'<div class="bar"><span style="width:{width}%"></span></div>'
        f'<div class="chart-value">{_e(str(_fmt(value)))}</div></div>'
    )


def _workflow_svg() -> str:
    return """
<svg width="900" height="330" viewBox="0 0 900 330" role="img" aria-label="Interactive agent workflow">
  <defs>
    <marker id="workflow-arrow" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto">
      <path d="M0,0 L9,4.5 L0,9 Z" fill="#2558c7"></path>
    </marker>
  </defs>
  <g class="diagram-node active" data-phase="data">
    <rect x="35" y="40" width="130" height="58" rx="8" fill="#ffffff" stroke="#d9dee7"></rect>
    <text x="100" y="73" text-anchor="middle">Data</text>
  </g>
  <g class="diagram-node" data-phase="analysts">
    <rect x="235" y="40" width="150" height="58" rx="8" fill="#ffffff" stroke="#d9dee7"></rect>
    <text x="310" y="73" text-anchor="middle">Analysts</text>
  </g>
  <g class="diagram-node" data-phase="research">
    <rect x="455" y="40" width="150" height="58" rx="8" fill="#ffffff" stroke="#d9dee7"></rect>
    <text x="530" y="73" text-anchor="middle">Research</text>
    <path d="M530,98 C530,155 455,155 455,98" fill="none" stroke="#8a3d64" stroke-width="2" marker-end="url(#workflow-arrow)"></path>
  </g>
  <g class="diagram-node" data-phase="plan">
    <rect x="675" y="40" width="150" height="58" rx="8" fill="#ffffff" stroke="#d9dee7"></rect>
    <text x="750" y="73" text-anchor="middle">Plan</text>
  </g>
  <g class="diagram-node" data-phase="risk">
    <rect x="455" y="220" width="150" height="58" rx="8" fill="#ffffff" stroke="#d9dee7"></rect>
    <text x="530" y="253" text-anchor="middle">Risk</text>
    <path d="M605,249 C700,249 700,195 605,195" fill="none" stroke="#8a3d64" stroke-width="2" marker-end="url(#workflow-arrow)"></path>
  </g>
  <g class="diagram-node" data-phase="decision">
    <rect x="235" y="220" width="150" height="58" rx="8" fill="#ffffff" stroke="#d9dee7"></rect>
    <text x="310" y="253" text-anchor="middle">Decision</text>
  </g>
  <path d="M165,69 L235,69" stroke="#2558c7" stroke-width="2" marker-end="url(#workflow-arrow)"></path>
  <path d="M385,69 L455,69" stroke="#2558c7" stroke-width="2" marker-end="url(#workflow-arrow)"></path>
  <path d="M605,69 L675,69" stroke="#2558c7" stroke-width="2" marker-end="url(#workflow-arrow)"></path>
  <path d="M750,98 C750,175 530,175 530,220" fill="none" stroke="#2558c7" stroke-width="2" marker-end="url(#workflow-arrow)"></path>
  <path d="M455,249 L385,249" stroke="#2558c7" stroke-width="2" marker-end="url(#workflow-arrow)"></path>
  <text x="492" y="171" text-anchor="middle">research debate loop</text>
  <text x="681" y="200" text-anchor="middle">risk loop</text>
</svg>
"""


def _interaction_script() -> str:
    return """
(() => {
  const root = document.querySelector("#agent-workflow");
  if (!root) return;
  const steps = Array.from(root.querySelectorAll(".step[data-phase]"));
  const cards = Array.from(root.querySelectorAll("[data-phase-card]"));
  const nodes = Array.from(root.querySelectorAll(".diagram-node"));

  function selectPhase(phase) {
    steps.forEach((step) => step.classList.toggle("active", step.dataset.phase === phase));
    cards.forEach((card) => card.classList.toggle("active", card.dataset.phaseCard === phase));
    nodes.forEach((node) => {
      const active = node.dataset.phase === phase;
      node.classList.toggle("active", active);
      node.classList.toggle("muted", !active);
    });
  }

  steps.forEach((step) => {
    step.addEventListener("click", () => selectPhase(step.dataset.phase));
  });
  nodes.forEach((node) => {
    node.style.cursor = "pointer";
    node.addEventListener("click", () => selectPhase(node.dataset.phase));
  });
})();
"""


def _pct(value: Any) -> str:
    if value is None:
        return "N/A"
    return f"{_safe_float(value) * 100:.1f}%"


def _pct_value(value: Any) -> str:
    if value is None:
        return "N/A"
    return f"{_safe_float(value):.2f}%"


def _fmt(value: Any) -> Any:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.3g}"
    return value


def _compact_number(value: Any) -> str:
    if value is None:
        return "N/A"
    numeric = _safe_float(value)
    if abs(numeric) >= 1_000_000_000:
        return f"{numeric / 1_000_000_000:.2f}B"
    if abs(numeric) >= 1_000_000:
        return f"{numeric / 1_000_000:.2f}M"
    if abs(numeric) >= 1_000:
        return f"{numeric / 1_000:.2f}K"
    return _fmt(numeric)


def _ratio(numerator: Any, denominator: Any) -> float | None:
    denom = _safe_float(denominator)
    if denom == 0:
        return None
    return _safe_float(numerator) / denom


def _gap_pct(value: Any, baseline: Any) -> float | None:
    base = _safe_float(baseline)
    if base == 0:
        return None
    return (_safe_float(value) - base) / base * 100


def _first_sentence(value: Any) -> str:
    text = str(value or "")
    for delimiter in (". ", "; "):
        if delimiter in text:
            return text.split(delimiter, 1)[0] + delimiter.strip()
    return text


def _short_time(value: Any) -> str:
    text = str(value or "N/A")
    if len(text) > 22:
        return text[:22]
    return text


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _e(value: Any) -> str:
    return escape(str(value), quote=True)
