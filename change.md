# Change Log

## 2026-06-04 - Second Update: LangGraph Workflow

- Changed the active project workflow from the custom sequential runner to LangGraph.
- Added `mini_trading_agents/langgraph_workflow.py` as the main workflow builder.
- Changed `mini_trading_agents/workflow.py` into a compatibility import layer for the LangGraph workflow.
- Removed the old custom sequential runner file `mini_trading_agents/graph.py`.
- Cleaned `mini_trading_agents/logging.py` so it only keeps the streaming JSONL logger.
- Analyst stage now starts 4 analyst nodes in parallel:
  - `market_analyst`
  - `sentiment_analyst`
  - `news_analyst`
  - `fundamentals_analyst`
- Added a join from the parallel analyst stage into the research debate stage.
- Added multi-round bull/bear research debate loop:
  - `bull_researcher`
  - `bear_researcher`
  - configurable with `--research-turns`
- Added multi-round risk debate loop:
  - `aggressive_risk_debater`
  - `neutral_risk_debater`
  - `conservative_risk_debater`
  - configurable with `--risk-turns`
- Updated `TradingState.trace` to use a reducer so parallel nodes can append trace entries safely.
- Added debate turn limits to `TradingState`:
  - `max_research_debate_turns`
  - `max_risk_debate_turns`
- Changed runtime logging to consume LangGraph streaming output.
- Current JSONL logs are written from streamed graph chunks using `stream_mode=["updates", "values"]`.
- New stream log lifecycle events are `stream_start`, `stream_chunk`, and `stream_end`.
- Added `requirements.txt` with `langgraph>=1.2.2`.
- Kept the role count at 12 agent nodes.

## 2026-06-04 - Initial State

- Created the initial mini trading agents demo skeleton.
- Current workflow contains 12 agent role nodes:
  - 4 analysts: market/technical, sentiment, news, fundamentals.
  - 2 researchers: bull researcher and bear researcher.
  - 1 research manager.
  - 1 trader.
  - 3 risk debaters: aggressive, neutral, conservative.
  - 1 portfolio manager.
- Current workflow execution model is a simple sequential chain, not LangGraph yet.
- All nodes share one `TradingState` object and pass information by reading/writing state fields.
- Added JSONL audit logging through `mini_trading_agents.logging`.
- Current log events include `run_start`, `node_start`, `node_end`, and `run_end`.
- Added command-line demo entry point in `run_demo.py`.
- Added README documentation and `.gitignore`.
- Pushed the initial commit to GitHub repository `foubean/multi-mind-research.git` on branch `develop`.
