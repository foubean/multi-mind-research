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

Control debate loops:

```powershell
python .\run_demo.py --research-turns 4 --risk-turns 6
```

Persist snapshots and decision memory:

```powershell
python .\run_demo.py --ticker NVDA --date 2026-06-05 --run-id nvda-demo-001
python .\run_demo.py --resume nvda-demo-001
```

Snapshots are written to `storage/trading_agents.sqlite` by default. Each streamed full-state `values` chunk is saved as a recoverable snapshot, and the final decision is saved into decision memory.

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
- `mini_trading_agents/logging.py`: JSONL run logger for streamed graph events.
- `mini_trading_agents/agents.py`: role implementations.
- `run_demo.py`: command-line demo entry point.

## Extending

Replace the deterministic report logic in `agents.py` with calls to an LLM. Add more adapters under the relevant data category directory, such as `mini_trading_agents/data_layer/news/`, and have `prepare_data` write normalized inputs into `TradingState` before the analyst fan-out.
