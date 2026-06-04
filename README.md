# Mini Trading Agents Demo

A minimal LangGraph skeleton inspired by TradingAgents.

It demonstrates three core ideas:

- Multiple role-specific agents run in a graph workflow.
- Agents share information through one mutable workflow state.
- Later agents synthesize earlier reports, debates, proposals, and risk reviews.
- Analyst nodes run in parallel, while research and risk debate nodes loop for
  configurable rounds.

This is a teaching/demo scaffold, not investment advice and not a live trading
system.

## Run

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

```powershell
python .\run_demo.py --ticker NVDA --date 2026-01-15
```

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

## Workflow

```text
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
- `mini_trading_agents/langgraph_workflow.py`: LangGraph workflow with parallel
  analysts and debate loops.
- `mini_trading_agents/logging.py`: JSONL run logger for streamed graph events.
- `mini_trading_agents/agents.py`: role implementations.
- `run_demo.py`: command-line demo entry point.

## Extending

Replace the deterministic functions in `agents.py` with calls to an LLM, data
provider, or a real LangGraph node. Keep the same state keys and the rest of the
pipeline can remain unchanged.
