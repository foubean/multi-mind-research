# Mini Trading Agents Demo

A minimal LangGraph skeleton inspired by TradingAgents.

It demonstrates three core ideas:

- Multiple role-specific agents run in a graph workflow.
- Agents share information through one mutable workflow state.
- Later agents synthesize reports, debates, proposals, and risk reviews.
- Analyst nodes run in parallel, while research and risk debate nodes loop for configurable rounds.

This is a teaching/demo scaffold, not investment advice and not a live trading system.

## Run

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Run with local sample data:

```powershell
python .\run_demo.py --ticker NVDA --date 2026-01-15
```

Run with Yahoo Finance adapters:

```powershell
python .\run_demo.py --ticker NVDA --date 2026-01-15 --data-provider yahoo
```

Choose providers per data category:

```powershell
python .\run_demo.py --ticker NVDA --date 2026-01-15 --market-provider yahoo --sentiment-provider yahoo --news-provider sample --fundamentals-provider yahoo
```

`--data-provider` is a shortcut that sets all four categories. Category-specific flags override it.

Create a local config from the example:

```powershell
Copy-Item .\config.example.toml .\config.toml
```

Enable real LLM-backed decision nodes by editing local `config.toml`:

```toml
[llm]
enabled = true
runtime_check_enabled = true
provider = "openai"
model = "gpt-5.5"
api_key_env = "OPENAI_API_KEY"
temperature = 0.2
```

Then set the API key in your shell before running:

```powershell
$env:OPENAI_API_KEY = "..."
python .\run_demo.py --ticker NVDA --date 2026-06-05
```

Because local `config.toml` is ignored by git, you can also put a direct key there:

```toml
api_key = "sk-..."
```

Test the configured OpenAI-compatible connection without running the full workflow:

```powershell
python .\scripts\test_openai_connection.py --config .\config.toml
```

When enabled, every role node can use the OpenAI Responses API with structured JSON output. This includes analysts, bull/bear researchers, research manager, trader, risk debaters, and portfolio manager.

If an LLM call fails while enabled, the workflow stops with an error. There is no automatic fallback in LLM mode.

When `runtime_check_enabled = true`, the runner sends one small LLM check before the graph starts. This catches unavailable LLM services before data preparation, debate loops, and other workflow work begin.

Data provider status can be:

- `ok`: all requested data categories came from the selected provider.
- `partial`: at least one data category fell back to sample data.
- `fallback`: reserved for future hard provider-level fallback handling.

Yahoo currently fills all four data categories:

- market: historical prices and derived technical indicators.
- sentiment: market-proxy sentiment from ticker momentum plus VIX.
- news: Yahoo Finance news normalized into `NewsData`.
- fundamentals: Yahoo `info` and financial statements normalized into `FundamentalsData`.

Yahoo news and sentiment are useful for this demo, but still lightweight. Production use should add SEC filings, a dedicated news API, and a real social/news sentiment model.

Each run writes a JSONL audit log to `logs/` by default:

```powershell
python .\run_demo.py --ticker NVDA --date 2026-01-15 --pretty
Get-Content .\logs\<generated-file>.jsonl
```

Disable logs when you only want console output:

```powershell
python .\run_demo.py --no-log
```

Each successful run also writes a self-contained HTML report to `reports/`. The report includes quote-page style key data, clickable section navigation, an interactive agent workflow explorer, synchronized workflow/diagram/summary highlighting, multi-round debate loops, data lineage, LLM usage, headline metrics, and lightweight data charts. `reports/` is ignored by git because the files are run artifacts.

Each normalized data slice includes lightweight lineage metadata. The lineage records provider, adapter, raw source, fetch time, downstream analyst, optional raw reference, and key transforms used to derive fields such as moving averages, sentiment score, news sentiment, and fundamentals ratios.

## Data Lineage Design

The current lineage model is intentionally lightweight. It is data-slice-level lineage, not full decision-DAG lineage.

Each normalized data object carries a `lineage` field:

```text
provider/raw source
  -> adapter
  -> normalized data fields
  -> analyst node
```

This is enough for the current workflow because the system has a short data path, limited iteration depth, and no repeated reuse of the same data slice across many independent decision branches. At this stage the most important audit questions are:

- where the data came from.
- which adapter fetched or normalized it.
- which fields were derived and how.
- which analyst consumed the data.
- whether the HTML report can trace conclusions back to the source data slice.

The current implementation does not yet model the full downstream decision graph:

```text
raw_data_id
  -> normalized_data_id
  -> analyst_report_id
  -> debate_turn_id
  -> trader_proposal_id
  -> risk_assessment_id
  -> final_decision_id
```

That heavier DAG-style lineage should be added later if the system starts doing long-running simulation, repeated backtests, multi-source fusion, distributed execution, or historical impact analysis where one bad upstream data point must be traced across many reports, debates, and decisions.

## Local Paper Trading

The local paper trading layer is independent from the agent workflow. Agents still only produce `final_trade_decision`; the execution layer consumes the final state after the graph finishes.

```text
final_trade_decision
  -> LocalPaperAdapter
  -> paper order / fill / position / portfolio snapshot
  -> paper_trading_result
  -> HTML report
```

The first implementation is long-only and deterministic. It uses a simple
demo-only conversion from the single-ticker conviction bucket to a local target
weight so the adapter can create fills and portfolio snapshots:

- `BUY` maps `position_size` to a local paper target weight.
- `SELL` maps to a zero target weight, which closes the local long position.
- `HOLD` creates no new order.
- `none`, `small`, `medium`, and `large` map to 0%, 10%, 25%, and 50%.
- `market_data.close` is used as the reference fill price.
- fee and slippage are configurable.
- repeated runs with the same `run_id` and account return the saved paper order result instead of submitting a duplicate order.

Enable it in local `config.toml`:

```toml
[paper_trading]
enabled = true
provider = "local"
account_id = "demo"
initial_cash = 100000
base_currency = "USD"
fee_rate = 0.0005
slippage_bps = 5
allow_fractional = true
```

Paper trading uses the same custom SQLite database configured by `persistence.storage_path`. It creates independent tables named `paper_accounts`, `paper_positions`, `paper_orders`, `paper_fills`, and `portfolio_snapshots`. When enabled, the HTML report includes a `Paper Trading` section with account, order, position, and PnL summary.

The execution layer is adapter-based. `provider = "local"` uses the local SQLite paper adapter. `provider = "alpaca"` uses Alpaca's paper trading REST API and reads credentials from environment variables by default:

```toml
[paper_trading]
enabled = true
provider = "alpaca"
allow_fractional = true

[paper_trading.alpaca]
api_key_env = "ALPACA_API_KEY"
api_secret_env = "ALPACA_API_SECRET"
base_url = "https://paper-api.alpaca.markets"
```

The Alpaca adapter submits market day orders, uses `client_order_id` for run-level idempotency, refreshes account and position data after submission, and attempts to read one month of daily portfolio history for report metadata.

## Single-Ticker Trade Advice

The single-ticker graph should not decide final portfolio weights in a multi-asset system. Its job is to analyze one ticker and produce structured trade advice that a future parent portfolio graph can compare against other tickers.

Trade preferences come from local config:

```toml
[parameters]
scope = "node" # node | global

[trade_preferences]
risk_profile = "balanced"
trading_style = "staged"
target_return_pct = 0.12
max_drawdown_pct = 0.08
expected_holding_days = 20
```

`parameters.scope = "node"` keeps the current single-ticker behavior where each
run uses its own node-level preferences. `parameters.scope = "global"` is only a
reserved placeholder for future parent-graph/global parameter handling and does
not change the current workflow yet.

The trader node now emits `trade_advice` with:

- action and conviction bucket: `BUY/HOLD/SELL` plus `none/small/medium/large`.
- trade intent: `open/add/reduce/exit/watch/wait`. `HOLD + watch` is the current observation/standby case.
- expected return, expected risk, and expected holding days. Return/risk values
  are fractional values for that configured holding period, not annualized and
  not 3/5/10-year projections, so `0.10` means 10% over `expected_holding_days`.
- risk profile and trading style.
- entry, add, reduce, and stop-loss plans.
- invalidation conditions.

`position_size` remains a conviction bucket for the single ticker, not a final
portfolio allocation. The local paper adapter may temporarily translate that
bucket into a demo target weight, but a future parent portfolio graph should be
the only layer that converts multiple tickers' advice into precise
`target_weight` values under portfolio constraints.

## Global Portfolio Graph

`run_portfolio_demo.py` runs a portfolio-level parent graph that treats the
single-ticker LangGraph as a reusable computation node. The parent graph fans
out ticker tasks, collects each ticker's `trade_advice`, builds portfolio
context, asks a portfolio manager for final target weights, validates hard
constraints, revises repairable plans, and emits an execution plan plus a
portfolio HTML report.

```powershell
python .\run_portfolio_demo.py --config .\config.example.toml --tickers NVDA,AAPL,MSFT --date 2026-06-05 --data-provider sample
```

The portfolio manager uses the configured LLM when `[llm].enabled = true`; if
LLM is disabled, the script uses a deterministic demo plan so the graph skeleton
can be tested without API keys. Hard constraints are checked before ticker
fan-out and again after the portfolio plan:

```toml
[portfolio]
max_revision_count = 2
single_ticker_failure_policy = "fail_fast"

[portfolio.constraints]
long_only = true
max_single_position_pct = 0.25
max_total_equity_pct = 0.85
cash_reserve_pct = 0.05
max_turnover_pct = 0.2
max_new_positions = 5
min_order_value = 100
```

The parent graph now has three validation layers:

- `preflight_validate`: checks ticker list, no-trade symbols, data provider
  config, LLM config, and portfolio constraint sanity before expensive work.
- `validate_portfolio_plan`: checks target weights, cash reserve, long-only,
  single-position caps, max new positions, and plan turnover.
- `validate_execution_plan`: checks order-level feasibility such as turnover and
  minimum order value before execution handoff.

`load_account_context` first tries to read local paper-trading account,
positions, and recent portfolio snapshots from `persistence.storage_path`. If no
paper account exists yet, it falls back to configured initial cash. The global
report includes cross-section rankings, action distribution, risk and execution
validation, single-ticker node drilldown, target weights, and planned orders.

`run_portfolio_demo.py` uses LangGraph streaming with checkpoint, custom
snapshot, and decision memory/store support, matching the single-ticker runner's
persistence model. Portfolio-level memory events use
`scope_type = "portfolio"` and `scope_id = "global"`.

The LLM portfolio manager is the soft decision layer. Deterministic validation is
the hard constraint layer. The validator should not silently invent a portfolio;
it classifies violations and either routes to revision or rejects an infeasible
plan with the partial ticker results preserved.

Control debate loops:

```powershell
python .\run_demo.py --research-turns 4 --risk-turns 6
```

Persist snapshots and decision memory:

```powershell
python .\run_demo.py --ticker NVDA --date 2026-06-05 --run-id nvda-demo-001
python .\run_demo.py --resume nvda-demo-001
```

Snapshots are written to `storage/trading_agents.sqlite` by default. Each streamed full-state `values` chunk is saved as a recoverable snapshot. Decision memory is written to LangGraph Store at `storage/langgraph_memory.sqlite`; the custom SQLite database also keeps `decision_memory` and `memory_events` rows as an audit-friendly copy with metadata such as ticker, analysis date, analyst signals, risk status, action, position size, and confidence.

Persistence is configured in local `config.toml`. The three persistence layers are all enabled by default:

- `checkpoint_enabled`: LangGraph native checkpoints keyed by `thread_id`.
- `snapshot_enabled`: custom complete-state snapshots after streamed `values` chunks.
- `decision_memory_enabled`: final portfolio decisions saved to LangGraph Store, with an audit copy in custom SQLite.

Use a different config file when needed:

```powershell
python .\run_demo.py --config .\config.toml --ticker NVDA
```

## Workflow

```text
Prepare Data
        |
        v
Market Analyst
Sentiment Analyst
News Analyst
Fundamentals Analyst
        |
        v
Bull Researcher <-> Bear Researcher
        |
        v
Research Manager
        |
        v
Trader
        |
        v
Aggressive / Neutral / Conservative Risk Debaters
        |
        v
Portfolio Manager
```

## Files

- `mini_trading_agents/state.py`: shared workflow state structures.
- `mini_trading_agents/data_layer/`: data acquisition, cleaning, and structuring layer.
- `mini_trading_agents/data_layer/market/`: market data adapters.
- `mini_trading_agents/data_layer/sentiment/`: sentiment data adapters.
- `mini_trading_agents/data_layer/news/`: news data adapters.
- `mini_trading_agents/data_layer/fundamentals/`: fundamentals data adapters.
- `mini_trading_agents/langgraph_workflow.py`: LangGraph workflow with parallel analysts and debate loops.
- `mini_trading_agents/config.py`: TOML config loader for persistence features.
- `mini_trading_agents/llm_adapter/`: provider adapters for optional LLM-backed decision nodes.
- `mini_trading_agents/logging.py`: JSONL run logger for streamed graph events.
- `mini_trading_agents/storage/`: custom SQLite snapshots and decision memory.
- `mini_trading_agents/agents.py`: role implementations.
- `config.example.toml`: safe example config for local `config.toml`.
- `run_demo.py`: command-line demo entry point.

## Extending

Replace the deterministic report logic in `agents.py` with calls to an LLM. Add more adapters under the relevant data category directory, such as `mini_trading_agents/data_layer/news/`, and have `prepare_data` write normalized inputs into `TradingState` before the analyst fan-out.

接入RL
state = 市场状态 + agent reports + memory
action = BUY / SELL / HOLD + position_size
reward = 未来收益 - 风险惩罚 - 交易成本
policy = 可训练模型
