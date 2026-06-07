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
