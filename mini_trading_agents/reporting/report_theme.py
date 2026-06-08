STYLE = """
:root {
  --bg: #f4f5f7;
  --surface: #ffffff;
  --surface-soft: #f8fafc;
  --ink: #181f2a;
  --muted: #687386;
  --line: #d9dee7;
  --buy: #12805c;
  --hold: #8a6217;
  --sell: #b33535;
  --accent: #2558c7;
  --accent-soft: #eaf0ff;
  --risk: #8a3d64;
  --warn: #b7791f;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  line-height: 1.45;
}
html { scroll-behavior: smooth; }
.page { max-width: 1280px; margin: 0 auto; padding: 24px 24px 48px; }
.market-shell {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 14px 36px rgba(30, 41, 59, .08);
}
.quote-header {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(280px, .8fr);
  gap: 20px;
  padding: 24px;
  border-bottom: 1px solid var(--line);
}
.symbol-line { color: var(--muted); font-size: 13px; margin-bottom: 8px; }
.quote-title { margin: 0 0 16px; font-size: 32px; letter-spacing: 0; line-height: 1.15; }
.quote-row { display: flex; align-items: end; gap: 14px; flex-wrap: wrap; }
.price { font-size: 42px; line-height: 1; font-weight: 800; letter-spacing: 0; }
.change { font-size: 18px; font-weight: 750; padding-bottom: 5px; }
.positive, .BUY, .bullish { color: var(--buy); }
.negative, .SELL, .bearish { color: var(--sell); }
.HOLD, .neutral { color: var(--hold); }
.market-note { margin-top: 12px; color: var(--muted); font-size: 13px; }
.decision-card {
  border-left: 4px solid var(--accent);
  background: var(--surface-soft);
  padding: 18px;
  border-radius: 8px;
  display: grid;
  gap: 9px;
}
.decision-card .label, .metric .label, .data-row span:first-child {
  color: var(--muted);
  font-size: 12px;
  text-transform: uppercase;
}
.decision-card .action { font-size: 30px; font-weight: 850; }
.subnav {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  padding: 0 24px;
  border-bottom: 1px solid var(--line);
  background: #fbfcff;
}
.subnav a {
  padding: 13px 12px;
  font-size: 13px;
  color: var(--muted);
  border-bottom: 2px solid transparent;
  text-decoration: none;
}
.subnav a:hover, .subnav a.active { color: var(--accent); border-color: var(--accent); font-weight: 700; }
.section { margin-top: 20px; }
.section, .market-shell { scroll-margin-top: 18px; }
.section h2 { margin: 0 0 12px; font-size: 19px; letter-spacing: 0; }
.panel, .node, .metric, .debate-item, .stage {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 8px;
}
.panel { padding: 18px; }
.grid { display: grid; gap: 16px; }
.grid-2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.grid-3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.grid-4 { grid-template-columns: repeat(4, minmax(0, 1fr)); }
.trade-advice-overview { display: grid; grid-template-columns: repeat(2, minmax(280px, 1fr)); gap: 16px; }
.trade-plan-grid { display: grid; grid-template-columns: repeat(2, minmax(320px, 1fr)); gap: 16px; margin-top: 16px; }
.trade-plan-card { display: grid; gap: 12px; align-content: start; }
.trade-plan-meta { display: grid; grid-template-columns: repeat(2, minmax(0, 180px)); gap: 10px; }
.trade-plan-card .metric { min-height: 76px; }
.trade-plan-card .metric .value { font-size: 16px; line-height: 1.3; overflow-wrap: anywhere; }
.trade-trigger {
  border: 1px solid #edf0f5;
  border-radius: 8px;
  background: var(--surface-soft);
  padding: 12px;
}
.trade-trigger .label {
  color: var(--muted);
  font-size: 12px;
  text-transform: uppercase;
  margin-bottom: 6px;
}
.trade-trigger p { margin: 0; color: var(--ink); font-size: 14px; line-height: 1.55; overflow-wrap: anywhere; }
.quote-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; padding: 20px 24px 24px; }
.data-table { display: grid; gap: 11px; }
.data-row { display: flex; justify-content: space-between; gap: 16px; border-bottom: 1px solid #edf0f5; padding-bottom: 9px; }
.data-row:last-child { border-bottom: 0; padding-bottom: 0; }
.data-row strong { text-align: right; overflow-wrap: anywhere; }
.range-card { display: grid; gap: 14px; }
.range-label { display: flex; justify-content: space-between; color: var(--muted); font-size: 13px; }
.range-track { position: relative; height: 10px; border-radius: 99px; background: #e8edf5; overflow: hidden; }
.range-track span { display: block; height: 100%; background: var(--accent); border-radius: 99px; }
.metric { padding: 14px; min-height: 94px; }
.metric .value { font-size: 22px; font-weight: 780; margin-top: 8px; }
.metric .summary { margin-top: 6px; }
.node { padding: 15px; min-height: 172px; display: grid; align-content: start; gap: 8px; }
.node h3, .panel h3, .stage h3 { margin: 0; font-size: 15px; }
.tag { display: inline-flex; width: fit-content; padding: 3px 8px; border-radius: 999px; font-size: 12px; background: var(--accent-soft); color: var(--accent); font-weight: 650; }
.summary { color: var(--muted); font-size: 13px; }
.bar { height: 8px; background: #edf1f7; border-radius: 99px; overflow: hidden; }
.bar span { display: block; height: 100%; background: var(--accent); }
.workflow-explorer { display: grid; gap: 16px; }
.workflow {
  display: grid;
  grid-template-columns: repeat(6, minmax(120px, 1fr));
  gap: 10px;
}
.step {
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 12px;
  background: #fbfcff;
  min-height: 86px;
  position: relative;
  color: inherit;
  cursor: pointer;
  text-align: left;
  font: inherit;
  transition: border-color .16s ease, box-shadow .16s ease, transform .16s ease, background .16s ease;
}
.step:hover, .step.active {
  border-color: var(--accent);
  background: var(--accent-soft);
  box-shadow: 0 8px 22px rgba(37, 88, 199, .13);
  transform: translateY(-1px);
}
.step strong { display: block; font-size: 13px; }
.step small { color: var(--muted); }
.stage { padding: 18px; min-height: 180px; display: none; gap: 10px; align-content: start; }
.stage.active { display: grid; }
.stage .nodes { color: var(--muted); font-size: 12px; }
.stage-metrics { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.stage-metrics .metric { min-height: 76px; }
.stage-detail { display: grid; gap: 10px; }
.stage-stack { display: block; }
.debate-list { display: grid; gap: 10px; }
.debate-item { padding: 13px; border-left: 4px solid var(--accent); }
.debate-item.bear, .debate-item.conservative { border-left-color: var(--risk); }
.svg-wrap { overflow-x: auto; }
.workflow-explorer .svg-wrap { margin-top: 16px; border-top: 1px solid var(--line); padding-top: 14px; }
svg text { font-family: inherit; fill: var(--ink); font-size: 12px; }
.diagram-node rect, .diagram-node path { transition: fill .16s ease, stroke .16s ease, stroke-width .16s ease, filter .16s ease; }
.diagram-node.active rect {
  fill: var(--accent-soft);
  stroke: var(--accent);
  stroke-width: 3;
  filter: drop-shadow(0 8px 12px rgba(37, 88, 199, .16));
}
.diagram-node.active path { stroke: var(--accent); stroke-width: 3; }
.diagram-node.muted { opacity: .42; }
.chart-row { display: grid; grid-template-columns: 120px 1fr 70px; gap: 10px; align-items: center; margin: 9px 0; }
.chart-label { color: var(--muted); font-size: 13px; }
.chart-value { text-align: right; font-weight: 650; }
.source-note { color: var(--muted); font-size: 12px; margin-top: 10px; }
.lineage-grid { display: grid; grid-template-columns: 1fr; gap: 16px; }
.lineage-card { display: grid; gap: 12px; align-content: start; }
.lineage-card h3 { margin: 0; font-size: 15px; }
.lineage-transforms { display: grid; gap: 8px; }
.lineage-transform {
  border-left: 3px solid var(--accent);
  background: var(--surface-soft);
  border-radius: 6px;
  padding: 9px 10px;
}
.lineage-transform strong { display: block; font-size: 13px; }
.lineage-transform span { color: var(--muted); font-size: 12px; }
.back-top {
  position: fixed;
  right: 42px;
  bottom: 56px;
  width: 52px;
  height: 52px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: var(--accent);
  color: #ffffff;
  text-decoration: none;
  font-size: 24px;
  font-weight: 800;
  box-shadow: 0 18px 34px rgba(37, 88, 199, .34);
  z-index: 20;
}
.back-top:hover { background: #1e49a7; }
@media (max-width: 920px) {
  .quote-header, .quote-grid, .grid-2, .grid-3, .grid-4, .trade-advice-overview, .trade-plan-grid { grid-template-columns: 1fr; }
  .trade-plan-meta { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .workflow { grid-template-columns: 1fr 1fr; }
  .price { font-size: 34px; }
  .back-top { right: 22px; bottom: 34px; }
}
"""

SIGNAL_LABELS = {
    "bullish": "Bullish",
    "neutral": "Neutral",
    "bearish": "Bearish",
}

PHASES = [
    ("Data", "prepare_data", "Collect normalized market, sentiment, news, and fundamentals slices."),
    ("Analysts", "market / sentiment / news / fundamentals", "Produce four independent evidence reports."),
    ("Research", "bull_researcher / bear_researcher", "Run a multi-turn investment debate around upside and downside cases."),
    ("Plan", "research_manager / trader", "Convert debate output into an investment plan and trade proposal."),
    ("Risk", "aggressive / neutral / conservative", "Stress-test position sizing and execution risk."),
    ("Decision", "portfolio_manager", "Approve, revise, or reject the proposed action."),
]
