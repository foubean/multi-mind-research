# Sample Data Layer

This directory shows the planned input data shape for the four analyst nodes.
The current demo still uses deterministic mock logic in `mini_trading_agents/agents.py`;
these files document the next data-provider layer.

Recommended graph position:

```text
START
  -> prepare_data
  -> market_analyst / sentiment_analyst / news_analyst / fundamentals_analyst
  -> research debate
```

`prepare_data` should fetch, normalize, and write these objects into
`TradingState`. Each analyst then reads its own data object and writes its
report back to state.

## Files And Usage

| File | State key | Consumer | Purpose |
| --- | --- | --- | --- |
| `market_data.sample.json` | `market_data` | `market_analyst` | Price, volume, trend, momentum, and volatility context. |
| `sentiment_data.sample.json` | `sentiment_data` | `sentiment_analyst` | Social/forum/news-comment mood, mention counts, and dominant topics. |
| `news_data.sample.json` | `news_data` | `news_analyst` | Recent company, industry, and macro event summaries with source links. |
| `fundamentals_data.sample.json` | `fundamentals_data` | `fundamentals_analyst` | Revenue, margin, valuation, leverage, and cash-flow context. |

## Minimal Field Contract

Every data object should include:

- `ticker`: the asset being analyzed.
- `as_of`: the data snapshot date.
- `source`: where the data came from, such as `mock`, `provider_name`, or `internal_cache`.
- `observations`: human-readable facts that an analyst or LLM prompt can use directly.

Structured numeric fields are added around this minimum contract so future
rules, scoring, backtests, and LLM prompts can reuse the same state data.

## Intended State Flow

```python
state["market_data"] = market_data
state["sentiment_data"] = sentiment_data
state["news_data"] = news_data
state["fundamentals_data"] = fundamentals_data
```

Then:

```python
market_analyst(state)       # reads market_data, writes market_report
sentiment_analyst(state)    # reads sentiment_data, writes sentiment_report
news_analyst(state)         # reads news_data, writes news_report
fundamentals_analyst(state) # reads fundamentals_data, writes fundamentals_report
```
