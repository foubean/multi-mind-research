# Change Log

## 2026-06-07 - Twenty Sixth Update: Data Lineage Metadata

- Added `mini_trading_agents/data_layer/lineage.py` for shared lineage metadata creation.
- Added `Lineage` and `LineageTransform` state types.
- Added lineage metadata to sample data loading and all Yahoo data adapters.
- Each normalized data slice now records provider, adapter, raw source, fetch time, downstream analyst, optional raw reference, and key transforms.
- Added a `Data Lineage` section to the HTML report with per-slice source and transform cards.
- Added `Data Lineage` to the report navigation.

## 2026-06-06 - Twenty Fifth Update: HTML Report Output

- Added `mini_trading_agents/reporting/` for self-contained HTML report generation.
- Added `reporting/report_theme.py` to keep report style, visual tokens, and layout rules stable.
- Added automatic HTML report output under `reports/` after successful workflow runs.
- Added workflow overview, debate loop diagram, node summaries, LLM usage, final decision, and target data dashboards.
- Added inline metric and bar-chart rendering for market, sentiment, news, and fundamentals data.
- Refined the HTML layout toward a financial quote-page structure: quote header, key data table, technical position bars, stage summaries, workflow visualization, and debate details.
- Added clickable report navigation anchors and an interactive workflow explorer that synchronizes selected workflow steps, SVG diagram highlights, and the active stage summary card.
- Moved investment and risk debate loops into their corresponding Research and Risk summary cards, removing isolated debate sections from the lower report page.
- Reworked the workflow explorer layout into a vertical stack: workflow controls first, diagram second, selected stage summary below.
- Added `/reports/` to `.gitignore`.
- No additional agent nodes were required; the report is rendered from the final `TradingState`.

## 2026-06-06 - Twenty Fourth Update: Final LLM Integration Shape

- Confirmed every role node now supports LLM mode.
- Kept the data layer and state contracts unchanged: analyst nodes still return `Report`, research/risk debaters still append debate history, and portfolio manager still writes `final_trade_decision`.
- Finalized the OpenAI provider implementation as `OpenAIAdapter` under `mini_trading_agents/llm_adapter/openai.py`.
- Finalized the adapter response method name as `response_wrapper`.
- Confirmed LLM model, base URL, direct API key, API key environment variable, and temperature all come from runtime config.
- Confirmed LLM-enabled failures stop execution instead of producing a deterministic fallback decision.

## 2026-06-06 - Twenty Third Update: LLM Runtime Check

- Added `llm.runtime_check_enabled`, defaulting to true.
- Added a startup LLM connectivity check before graph execution when LLM mode is enabled.
- Added `OpenAIAdapter.check_connection()` for the lightweight preflight request.
- The workflow now fails before data preparation and agent execution if the configured LLM service is unavailable.

## 2026-06-06 - Twenty Second Update: LLM Analysts

- Added LLM-backed behavior for `market_analyst`, `sentiment_analyst`, `news_analyst`, and `fundamentals_analyst`.
- Each analyst now returns the existing `Report` shape: title, signal, confidence, and summary.
- LLM analyst prompts consume the normalized data fields already produced by the data layer.
- Deterministic analyst logic remains available when LLM is disabled.
- All current role nodes now support LLM mode.

## 2026-06-06 - Twenty First Update: LLM Research Debaters

- Added LLM-backed behavior for `bull_researcher` and `bear_researcher`.
- Each research debater now asks the configured LLM for a structured `argument` when LLM is enabled.
- Arguments still append to `investment_debate_state.history`, preserving the existing debate loop contract.
- Deterministic bull/bear debate text remains available when LLM is disabled.
- At this point, every role after the four analyst nodes can use LLM when enabled.

## 2026-06-06 - Twentieth Update: LLM Risk Debaters

- Added LLM-backed behavior for `aggressive_risk_debater`, `neutral_risk_debater`, and `conservative_risk_debater`.
- Each risk debater now asks the configured LLM for a structured `risk_view` when LLM is enabled.
- Risk views still append to the existing `risk_debate_state.history`, preserving the current graph state contract.
- Deterministic risk debate text remains available when LLM is disabled.
- Added LLM usage trace records for the three risk debater nodes.

## 2026-06-06 - Nineteenth Update: Direct LLM API Key Support

- Added optional `api_key` support for local `config.toml`.
- Kept `api_key_env` support as the preferred example path.
- Updated `OpenAIAdapter` to prefer direct `api_key` and fall back to `api_key_env`.
- Added the same direct key support for provider-style config blocks.

## 2026-06-05 - Eighteenth Update: LLM Adapter Layout

- Replaced the temporary `mini_trading_agents/llm/openai_json.py` layout with `mini_trading_agents/llm_adapter/openai.py`.
- Kept provider-specific code under `llm_adapter` so later providers such as Gemini can be added cleanly.
- Removed provider adapter default model selection; the model must now come from config.
- Updated imports and README paths to use `llm_adapter`.
- Renamed the adapter entry point from `generate_json` to `response_wrapper` for clearer intent.
- Added an agent-side `_invoke_llm` helper so nodes pass payloads and schemas without exposing provider call details.
- Converted OpenAI access into an `OpenAIAdapter` class with a reusable client.
- Added `get_llm_adapter(...)` as the global adapter factory used by all LLM-backed agents.

## 2026-06-05 - Seventeenth Update: OpenAI Connection Test

- Added `scripts/test_openai_connection.py` to test Responses API connectivity without running the full workflow.
- Made the test script read either the project `[llm]` config or an OpenAI provider-style TOML config.
- Removed a hard-coded API key from the OpenAI adapter so credentials only come from environment variables.
- Documented the connection test command in README.

## 2026-06-05 - Sixteenth Update: LLM Failure Stops Run

- Removed the extra `llm.required` switch to keep LLM configuration small.
- Removed automatic fallback in LLM mode.
- Changed LLM-enabled runs to stop immediately when an LLM-backed node fails.
- Kept deterministic behavior only when `llm.enabled = false`.

## 2026-06-05 - Fifteenth Update: LLM Usage Trace

- Added `llm_usage_trace` to `TradingState`.
- Added success/fallback trace records for `research_manager`, `trader`, and `portfolio_manager`.
- Updated console output to show whether each LLM-backed node used the API or fell back to deterministic logic.
- Kept fallback behavior, but made it visible instead of silent.

## 2026-06-05 - Fourteenth Update: Root Local Config

- Changed the default config path from `conf/config.toml` to root `config.toml`.
- Added `config.example.toml` as the tracked safe example config.
- Added `/config.toml` to `.gitignore` so local LLM/API settings stay outside version control.
- Updated README examples to use root `config.toml`.

## 2026-06-05 - Thirteenth Update: Optional LLM Agent Adapter

- Added an optional LLM configuration section in the runtime config file.
- Added an OpenAI Responses API JSON adapter for LLM-backed decision nodes.
- Added `openai>=2.0.0` to dependencies.
- Added `llm_config` to `TradingState`.
- Passed LLM configuration into the initial workflow state.
- Updated `research_manager`, `trader`, and `portfolio_manager` to use LLM structured JSON outputs when enabled.
- Kept deterministic rule-based behavior as the default and as fallback when LLM calls are disabled or unavailable.
- Left analyst and debate nodes deterministic for now to keep the first API-backed version small and stable.

## 2026-06-05 - Twelfth Update: LangGraph Store Memory

- Changed the active long-term memory layer to LangGraph Store.
- Added `memory_store_path`, defaulting to `storage/langgraph_memory.sqlite`.
- Updated the graph compile step to pass both `checkpointer` and `store`.
- Saved each final decision event into LangGraph Store under `("decision_memory", "ticker", TICKER)`.
- Kept custom `decision_memory` and `memory_events` tables as audit-friendly copies.
- Reused the same structured decision event payload for both LangGraph Store memory and the audit copy.

## 2026-06-05 - Eleventh Update: Simple Metadata Memory Events

- Added a simple `memory_events` table for long-term memory facts.
- Kept the first memory event type intentionally small: `decision_event`.
- Added metadata for each decision memory event, including run id, ticker, analysis date, data providers, analyst signals, risk status, final action, position size, and confidence.
- Updated `save_decision_memory` so one completed decision writes both the existing `decision_memory` row and a general `memory_events` row.
- Left retrieval, ranking, summaries, and LLM prompt injection for a later step.

## 2026-06-05 - Tenth Update: Trade Outcome Table Placeholder

- Added a reserved `trade_outcomes` table to the custom SQLite schema.
- Designed `trade_outcomes` as one simulated-trading result per `run_id`.
- Added fields for ticker, analysis date, final action, position size, entry/exit price, holding days, return percentage, max drawdown, reward, outcome label, notes, and raw outcome JSON.
- Added an index on `(ticker, analysis_date)` for future feedback and memory retrieval queries.
- This table is schema-only for now; the workflow does not write trade outcomes yet.

## 2026-06-05 - Ninth Update: Configurable Checkpoint Persistence

- Added a runtime configuration file for persistence settings.
- Added `mini_trading_agents/config.py` to load persistence settings with safe defaults.
- Added LangGraph native SQLite checkpoints through `SqliteSaver`.
- Updated `build_demo_workflow(checkpointer=None)` so the graph can compile with or without a checkpointer.
- Added `checkpoint_enabled`, `snapshot_enabled`, and `decision_memory_enabled` switches.
- Kept all three persistence switches enabled by default.
- Added `checkpoint_path` for LangGraph checkpoint storage.
- Kept `storage_path` for custom snapshots and decision memory.
- Updated `run_demo.py` to pass `thread_id = run_id` into LangGraph when checkpointing is enabled.
- Updated the streaming loop so custom snapshots are only written when `snapshot_enabled = true`.
- Updated final decision storage so decision memory is only written when `decision_memory_enabled = true`.
- Kept `--storage-path` as a CLI override for the configured custom persistence database.
- Added `--config` to select a TOML config file.

## 2026-06-05 - Eighth Update: SQLite Snapshots And Decision Memory

- Added local SQLite persistence under `mini_trading_agents/storage/`.
- Added `workflow_runs` table for run metadata and final state.
- Added `workflow_snapshots` table for complete streamed state snapshots.
- Added `decision_memory` table for final trade decisions.
- Added `--run-id` to give a run a stable id.
- Added `--resume RUN_ID` to restart from the latest complete snapshot state for a run id.
- Added `--storage-path`, defaulting to `storage/trading_agents.sqlite`.
- Updated the LangGraph streaming loop to save every `values` chunk as a snapshot.
- Persisted final decisions after successful run completion.
- Added `storage/` to `.gitignore`.

## 2026-06-04 - Seventh Update: Per-Category Provider CLI

- Changed runtime data-provider state from one `data_provider` string to a `data_providers` mapping.
- Added per-category CLI flags:
  - `--market-provider`
  - `--sentiment-provider`
  - `--news-provider`
  - `--fundamentals-provider`
- Kept `--data-provider` as a shortcut that sets all four categories.
- Updated `prepare_data` to choose adapters from each category's provider key.
- Updated data status output to report the full provider mapping.
- Updated README and `source.md` command examples.

## 2026-06-04 - Sixth Update: Category-Based Data Adapters

- Reworked the data layer from one provider class containing all data slices into category-specific adapters.
- Added separate data directories for `market`, `sentiment`, `news`, and `fundamentals`.
- Added per-category base adapter classes and sample/yahoo implementations.
- Moved Yahoo market logic into `data_layer/market/yahoo.py`.
- Moved Yahoo sentiment proxy logic into `data_layer/sentiment/yahoo.py`.
- Moved Yahoo news normalization into `data_layer/news/yahoo.py`.
- Moved Yahoo fundamentals normalization into `data_layer/fundamentals/yahoo.py`.
- Updated `prepare_data` to fetch each data category independently and fall back only the failing category.
- Removed the old unified `data_layer/providers/` provider implementation.
- Updated README and `source.md` to describe the category-based adapter structure.

## 2026-06-04 - Fifth Update: Analyst Data Source Planning

- Expanded `mini_trading_agents/data_layer/source.md` with engineering-oriented source planning for the three non-market analysts.
- Added recommended sources for `sentiment_analyst`, including VIX, put/call ratio, StockTwits, Reddit, AAII, ETF flows, 13F, and A-share social sources.
- Added recommended sources for `news_analyst`, including Yahoo Finance News, SEC EDGAR, NewsAPI, Google News RSS, Alpha Vantage, Benzinga, Bloomberg, Refinitiv, and A-share disclosure/news sources.
- Added recommended sources for `fundamentals_analyst`, including yfinance, SEC Company Facts, SEC filings, FRED, Damodaran data, FMP, Alpha Vantage, FactSet, Refinitiv, Bloomberg, AkShare, Tushare, Wind, and Choice.
- Added normalized target field examples for `SentimentData`, `NewsData`, and `FundamentalsData`.
- Added provider implementation guidance and a future `CompositeProvider` direction.
- Implemented Yahoo provider methods for the other three analyst data slices:
  - `fetch_sentiment_data` derives market-proxy sentiment from ticker momentum and VIX.
  - `fetch_news_data` reads Yahoo Finance news via yfinance and normalizes items into `NewsData`.
  - `fetch_fundamentals_data` reads yfinance info/statements and normalizes valuation, margin, leverage, cash, and free cash flow fields into `FundamentalsData`.
- Kept per-slice sample fallback when Yahoo data is unavailable or incomplete.

## 2026-06-04 - Fourth Update: Data Layer And Yahoo Finance

- Added `mini_trading_agents/data_layer/` as the data acquisition, cleaning, and structuring layer.
- Added provider factory pattern through `get_data_provider(provider_key)`.
- Added `DataProvider` base class with four required methods:
  - `fetch_market_data`
  - `fetch_sentiment_data`
  - `fetch_news_data`
  - `fetch_fundamentals_data`
- Added `SampleDataProvider` as the offline provider.
- Added `YahooFinanceProvider` as a provider adapter that overrides market data and explicitly falls back to sample data for sentiment, news, and fundamentals.
- Removed the earlier provider-specific `mini_trading_agents/data/yahoo_finance.py` layout.
- Added provider status semantics: `ok`, `partial`, and `fallback`.
- Added `prepare_data` graph node before the analyst fan-out.
- Updated graph shape to `START -> prepare_data -> parallel analysts -> research debate`.
- Added Yahoo Finance market data provider through `yfinance`.
- Yahoo provider fetches six months of daily history and structures close, change percent, volume, moving averages, RSI, MACD, volatility, and observations.
- Yahoo provider redirects the yfinance cache to local `.cache/yfinance` to avoid default cache permission errors.
- Added sample data loader as an offline fallback and local test source.
- Added `data_provider` and `data_status` to `TradingState`.
- Added structured data fields to `TradingState`: `market_data`, `sentiment_data`, `news_data`, and `fundamentals_data`.
- Updated analyst nodes to consume structured data when present.
- Added CLI option `--data-provider sample|yahoo`.
- Added `yfinance>=1.3.0` to `requirements.txt`.

## 2026-06-04 - Third Update: Sample Data Layer

- Added `sample/` directory to document the planned input data layer.
- Added sample market data for `market_analyst`.
- Added sample sentiment data for `sentiment_analyst`.
- Added sample news data for `news_analyst`.
- Added sample fundamentals data for `fundamentals_analyst`.
- Added `sample/README.md` to explain each sample file, its target `TradingState` key, consuming analyst, and intended report output.
- Documented the recommended future graph position: `START -> prepare_data -> parallel analysts`.
- Clarified the minimal data contract: `ticker`, `as_of`, `source`, and `observations`.

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
