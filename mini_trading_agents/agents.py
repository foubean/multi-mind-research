from __future__ import annotations

from statistics import mean
from typing import Any

from mini_trading_agents.llm_adapter import get_llm_adapter
from mini_trading_agents.state import DebateState, Report, TradingState


def _score_signal(signal: str) -> int:
    scores = {"bullish": 1, "neutral": 0, "bearish": -1}
    return scores[signal]


def _report(title: str, signal: str, confidence: float, summary: str) -> Report:
    return {
        "title": title,
        "signal": signal,
        "confidence": confidence,
        "summary": summary,
    }


def market_analyst(state: TradingState) -> TradingState:
    llm_report, llm_trace = _maybe_llm_analyst(
        state,
        "market_analyst",
        "Market/Technical Analyst",
        (
            "You are the market and technical analyst. Analyze price action, moving averages, "
            "RSI, MACD, volume, volatility, and the supplied market observations."
        ),
        {"market_data": state.get("market_data")},
    )
    if llm_report:
        return {"market_report": llm_report, "llm_usage_trace": [llm_trace]}

    ticker = state["ticker"]
    data = state.get("market_data")
    if data:
        close = data["close"]
        ma20 = data["moving_average_20"]
        signal = "bullish" if close >= ma20 else "bearish"
        confidence = 0.68 if signal == "bullish" else 0.6
        summary = f"{ticker} closed at {close}, with market observations: " + " ".join(data["observations"])
        return {"market_report": _report("Market/Technical Analyst", signal, confidence, summary)}

    return {
        "market_report": _report(
            "Market/Technical Analyst",
            "bullish",
            0.68,
            f"{ticker} shows constructive momentum with manageable volatility.",
        )
    }


def sentiment_analyst(state: TradingState) -> TradingState:
    llm_report, llm_trace = _maybe_llm_analyst(
        state,
        "sentiment_analyst",
        "Sentiment Analyst",
        (
            "You are the sentiment analyst. Analyze the supplied sentiment score, mention counts, "
            "topic mix, and sentiment observations."
        ),
        {"sentiment_data": state.get("sentiment_data")},
    )
    if llm_report:
        return {"sentiment_report": llm_report, "llm_usage_trace": [llm_trace]}

    ticker = state["ticker"]
    data = state.get("sentiment_data")
    if data:
        score = data["sentiment_score"]
        signal = "bullish" if score > 0.15 else "bearish" if score < -0.15 else "neutral"
        confidence = min(0.85, 0.55 + abs(score))
        summary = f"{ticker} sentiment score is {score}. " + " ".join(data["observations"])
        return {"sentiment_report": _report("Sentiment Analyst", signal, confidence, summary)}

    return {
        "sentiment_report": _report(
            "Sentiment Analyst",
            "neutral",
            0.55,
            f"Short-term discussion around {ticker} is active but mixed.",
        )
    }


def news_analyst(state: TradingState) -> TradingState:
    llm_report, llm_trace = _maybe_llm_analyst(
        state,
        "news_analyst",
        "News Analyst",
        (
            "You are the news analyst. Analyze recent news items, article sentiment, "
            "catalysts, and news-related risks from the supplied normalized news data."
        ),
        {"news_data": state.get("news_data")},
    )
    if llm_report:
        return {"news_report": llm_report, "llm_usage_trace": [llm_trace]}

    ticker = state["ticker"]
    data = state.get("news_data")
    if data:
        item_sentiments = [item["sentiment"] for item in data["items"]]
        positive = item_sentiments.count("positive")
        negative = item_sentiments.count("negative")
        signal = "bullish" if positive > negative else "bearish" if negative > positive else "neutral"
        confidence = 0.55 + min(0.25, abs(positive - negative) * 0.1)
        summary = f"{ticker} has {len(data['items'])} recent news items. " + " ".join(data["observations"])
        return {"news_report": _report("News Analyst", signal, confidence, summary)}

    return {
        "news_report": _report(
            "News Analyst",
            "bullish",
            0.62,
            f"Recent news flow for {ticker} is supportive, with no major negative catalyst.",
        )
    }


def fundamentals_analyst(state: TradingState) -> TradingState:
    llm_report, llm_trace = _maybe_llm_analyst(
        state,
        "fundamentals_analyst",
        "Fundamentals Analyst",
        (
            "You are the fundamentals analyst. Analyze growth, margins, valuation, leverage, "
            "cash flow, balance sheet quality, and the supplied fundamentals observations."
        ),
        {"fundamentals_data": state.get("fundamentals_data")},
    )
    if llm_report:
        return {"fundamentals_report": llm_report, "llm_usage_trace": [llm_trace]}

    ticker = state["ticker"]
    data = state.get("fundamentals_data")
    if data:
        growth = data["revenue_growth_yoy"]
        margin = data["operating_margin"]
        valuation = data["forward_pe"]
        signal = "bullish" if growth > 0.15 and margin > 0.2 else "neutral"
        confidence = 0.72 if valuation < 50 else 0.62
        summary = (
            f"{ticker} revenue growth is {growth:.1%}, operating margin is {margin:.1%}, "
            f"and forward P/E is {valuation}. "
            + " ".join(data["observations"])
        )
        return {"fundamentals_report": _report("Fundamentals Analyst", signal, confidence, summary)}

    return {
        "fundamentals_report": _report(
            "Fundamentals Analyst",
            "bullish",
            0.72,
            f"{ticker} has strong growth quality, though valuation requires discipline.",
        )
    }


def bull_researcher(state: TradingState) -> TradingState:
    reports = _analyst_reports(state)
    bullish_points = [r["summary"] for r in reports if r["signal"] == "bullish"]
    llm_argument, llm_trace = _maybe_llm_research_debater(
        state,
        "bull_researcher",
        (
            "You are the bull researcher. Build the strongest evidence-based bullish "
            "case from the analyst reports, while acknowledging the key condition "
            "that would weaken the thesis."
        ),
    )
    argument = llm_argument or "Bull case: " + " ".join(bullish_points)
    debate = _get_debate(state, "investment_debate_state")
    debate["history"].append(argument)
    debate["latest_speaker"] = "bull_researcher"
    debate["count"] += 1
    updates: TradingState = {"investment_debate_state": debate}
    if llm_trace:
        updates["llm_usage_trace"] = [llm_trace]
    return updates


def bear_researcher(state: TradingState) -> TradingState:
    debate = _get_debate(state, "investment_debate_state")
    llm_argument, llm_trace = _maybe_llm_research_debater(
        state,
        "bear_researcher",
        (
            "You are the bear researcher. Build the strongest evidence-based bearish "
            "or cautionary case from the analyst reports and existing debate, focusing "
            "on valuation, execution, sentiment, and downside risk."
        ),
    )
    argument = llm_argument or (
        "Bear case: sentiment is not decisive, valuation risk remains, and a better "
        "entry point may be needed."
    )
    debate["history"].append(argument)
    debate["latest_speaker"] = "bear_researcher"
    debate["count"] += 1
    updates: TradingState = {"investment_debate_state": debate}
    if llm_trace:
        updates["llm_usage_trace"] = [llm_trace]
    return updates


def research_manager(state: TradingState) -> TradingState:
    llm_result, llm_trace = _maybe_llm_research_manager(state)
    if llm_result:
        return {"investment_plan": llm_result, "llm_usage_trace": [llm_trace]}

    reports = _analyst_reports(state)
    weighted_score = _weighted_signal_score(reports)
    stance = _stance_from_score(weighted_score)
    updates: TradingState = {
        "investment_plan": {
            "stance": stance,
            "score": round(weighted_score, 3),
            "summary": (
                "Research conclusion combines analyst evidence with the bull/bear "
                f"debate and recommends a {stance} stance."
            ),
        }
    }
    if llm_trace:
        updates["llm_usage_trace"] = [llm_trace]
    return updates


def trader(state: TradingState) -> TradingState:
    llm_result, llm_trace = _maybe_llm_trader(state)
    if llm_result:
        return {"trader_investment_plan": llm_result, "trade_advice": llm_result, "llm_usage_trace": [llm_trace]}

    plan = state["investment_plan"]
    action = {"bullish": "BUY", "neutral": "HOLD", "bearish": "SELL"}[plan["stance"]]
    position_size = "small" if plan["score"] < 0.45 else "medium"
    confidence = min(0.9, 0.5 + abs(plan["score"]) / 2)
    advice = _build_trade_advice(
        state,
        action=action,
        position_size=position_size,
        confidence=confidence,
        rationale=plan["summary"],
    )
    updates: TradingState = {
        "trader_investment_plan": advice,
        "trade_advice": advice,
    }
    if llm_trace:
        updates["llm_usage_trace"] = [llm_trace]
    return updates


def aggressive_risk_debater(state: TradingState) -> TradingState:
    proposal = state["trader_investment_plan"]
    llm_view, llm_trace = _maybe_llm_risk_debater(
        state,
        "aggressive_risk_debater",
        (
            "You are the aggressive risk debater. You focus on upside capture, "
            "opportunity cost, and when accepting the proposed trade is justified. "
            "Still mention the main risk control that must be respected."
        ),
    )
    updates = _append_risk_view(
        state,
        "aggressive_risk_debater",
        llm_view
        or f"Aggressive view: accept the {proposal['position_size']} {proposal['action']} plan if momentum persists.",
    )
    if llm_trace:
        updates["llm_usage_trace"] = [llm_trace]
    return updates


def neutral_risk_debater(state: TradingState) -> TradingState:
    proposal = state["trader_investment_plan"]
    llm_view, llm_trace = _maybe_llm_risk_debater(
        state,
        "neutral_risk_debater",
        (
            "You are the neutral risk debater. You balance the upside case and "
            "downside risks, translating the trader proposal into practical risk "
            "conditions and invalidation criteria."
        ),
    )
    updates = _append_risk_view(
        state,
        "neutral_risk_debater",
        llm_view or f"Neutral view: keep the {proposal['action']} proposal but require clear invalidation criteria.",
    )
    if llm_trace:
        updates["llm_usage_trace"] = [llm_trace]
    return updates


def conservative_risk_debater(state: TradingState) -> TradingState:
    proposal = state["trader_investment_plan"]
    llm_view, llm_trace = _maybe_llm_risk_debater(
        state,
        "conservative_risk_debater",
        (
            "You are the conservative risk debater. You prioritize capital "
            "preservation, drawdown control, valuation risk, execution risk, and "
            "conditions that should reduce or reject exposure."
        ),
    )
    updates = _append_risk_view(
        state,
        "conservative_risk_debater",
        llm_view
        or f"Conservative view: cap exposure; {proposal['position_size']} is acceptable only with tight risk control.",
    )
    if llm_trace:
        updates["llm_usage_trace"] = [llm_trace]
    return updates


def portfolio_manager(state: TradingState) -> TradingState:
    llm_result, llm_trace = _maybe_llm_portfolio_manager(state)
    if llm_result:
        return {**llm_result, "llm_usage_trace": [llm_trace]}

    proposal = state["trader_investment_plan"]
    risk_count = state["risk_debate_state"]["count"]
    approved = proposal["confidence"] >= 0.6 and risk_count >= 3
    action = proposal["action"] if approved else "HOLD"
    position_size = proposal["position_size"] if approved else "none"
    confidence = round(mean([proposal["confidence"], 0.65]), 2)
    final_advice = dict(proposal)
    final_advice["action"] = action
    final_advice["position_size"] = position_size
    final_advice["confidence"] = confidence
    if not approved:
        final_advice["trade_intent"] = "watch"
        final_advice["rationale"] = "Risk review rejected the proposal; keep exposure at none."
    updates: TradingState = {
        "risk_assessment": {
            "status": "approved" if approved else "rejected",
            "notes": state["risk_debate_state"]["history"],
        },
        "final_trade_decision": {
            "action": action,
            "position_size": position_size,
            "confidence": confidence,
            "reason": (
                "Approved after analyst reports, research debate, trader proposal, "
                "and three-way risk review."
                if approved
                else "Rejected because confidence or risk review was insufficient."
            ),
        },
        "trade_advice": final_advice,
    }
    if llm_trace:
        updates["llm_usage_trace"] = [llm_trace]
    return updates


def _analyst_reports(state: TradingState) -> list[Report]:
    return [
        state["market_report"],
        state["sentiment_report"],
        state["news_report"],
        state["fundamentals_report"],
    ]


def _weighted_signal_score(reports: list[Report]) -> float:
    weighted = [_score_signal(r["signal"]) * r["confidence"] for r in reports]
    return mean(weighted)


def _stance_from_score(score: float) -> str:
    if score >= 0.25:
        return "bullish"
    if score <= -0.25:
        return "bearish"
    return "neutral"


def _get_debate(state: TradingState, key: str) -> DebateState:
    existing = state.get(key)
    if existing:
        return {
            "history": list(existing["history"]),
            "latest_speaker": existing["latest_speaker"],
            "count": existing["count"],
        }
    return {"history": [], "latest_speaker": "", "count": 0}


def _append_risk_view(state: TradingState, speaker: str, message: str) -> TradingState:
    debate = _get_debate(state, "risk_debate_state")
    debate["history"].append(message)
    debate["latest_speaker"] = speaker
    debate["count"] += 1
    return {"risk_debate_state": debate}


def _build_trade_advice(
    state: TradingState,
    *,
    action: str,
    position_size: str,
    confidence: float,
    rationale: str,
) -> dict[str, Any]:
    preferences = state.get("trade_preferences", {})
    risk_profile = str(preferences.get("risk_profile", "balanced"))
    trading_style = str(preferences.get("trading_style", "staged"))
    target_return = float(preferences.get("target_return_pct", 0.12))
    max_drawdown = float(preferences.get("max_drawdown_pct", 0.08))
    holding_days = int(preferences.get("expected_holding_days", 20))
    risk_multiplier = {"conservative": 0.7, "balanced": 1.0, "aggressive": 1.25}.get(risk_profile, 1.0)
    expected_return = target_return * confidence * risk_multiplier if action == "BUY" else 0.0
    expected_risk = max_drawdown * (1.0 if action == "BUY" else 0.4)
    return {
        "action": action,
        "trade_intent": _trade_intent(action),
        "position_size": position_size,
        "confidence": round(confidence, 3),
        "rationale": rationale,
        "expected_return_pct": round(expected_return, 4),
        "expected_risk_pct": round(expected_risk, 4),
        "expected_holding_days": holding_days,
        "risk_profile": risk_profile,
        "trading_style": trading_style,
        "entry_plan": _entry_plan(trading_style, action),
        "add_position_plan": _add_position_plan(trading_style, action),
        "reduce_position_plan": _reduce_position_plan(risk_profile),
        "stop_loss_plan": {
            "method": "technical_invalidation",
            "trigger": "Reduce or exit if price closes below the major moving-average support with heavy volume.",
            "fraction": 1.0 if risk_profile == "conservative" else 0.5,
        },
        "invalidation_conditions": _invalidation_conditions(state),
    }


def _entry_plan(trading_style: str, action: str) -> dict[str, Any]:
    if action != "BUY":
        return {"method": "no_new_entry", "trigger": "No long entry while action is not BUY.", "fraction": 0.0}
    if trading_style == "left_side":
        return {"method": "left_side_staged_entry", "trigger": "Start on controlled pullbacks near support.", "fraction": 0.3}
    if trading_style == "right_side":
        return {"method": "right_side_confirmation_entry", "trigger": "Enter after breakout or trend confirmation.", "fraction": 0.4}
    if trading_style == "breakout":
        return {"method": "breakout_entry", "trigger": "Enter only after breakout with volume confirmation.", "fraction": 0.5}
    if trading_style == "pullback":
        return {"method": "pullback_entry", "trigger": "Enter near MA20 or prior support if thesis remains intact.", "fraction": 0.4}
    return {"method": "staged_entry", "trigger": "Open partial exposure first, then wait for confirmation.", "fraction": 0.4}


def _trade_intent(action: str) -> str:
    if action == "BUY":
        return "open"
    if action == "SELL":
        return "exit"
    return "watch"


def _add_position_plan(trading_style: str, action: str) -> dict[str, Any]:
    if action != "BUY":
        return {"method": "no_add", "trigger": "No add-on while action is not BUY.", "fraction": 0.0}
    if trading_style in {"right_side", "breakout"}:
        return {"method": "right_side_add", "trigger": "Add after a higher high with participation above average.", "fraction": 0.3}
    return {"method": "staged_add", "trigger": "Add only if price confirms the thesis without breaking risk limits.", "fraction": 0.3}


def _reduce_position_plan(risk_profile: str) -> dict[str, Any]:
    if risk_profile == "conservative":
        return {"method": "early_trim", "trigger": "Trim quickly when momentum fades or drawdown approaches risk budget.", "fraction": 0.5}
    if risk_profile == "aggressive":
        return {"method": "trim_on_invalidation", "trigger": "Trim mainly on thesis deterioration or technical invalidation.", "fraction": 0.25}
    return {"method": "trim_on_strength_or_risk", "trigger": "Trim on overextension, valuation stress, or risk-budget pressure.", "fraction": 0.33}


def _invalidation_conditions(state: TradingState) -> list[str]:
    conditions = [
        "Price breaks below major moving averages on heavy volume.",
        "Analyst signal mix deteriorates from bullish/neutral toward bearish.",
        "Risk debate identifies unresolved downside or execution risk.",
    ]
    market = state.get("market_data", {})
    fundamentals = state.get("fundamentals_data", {})
    if market.get("rsi_14", 0) >= 65:
        conditions.append("Momentum becomes overextended without confirmation from volume.")
    if fundamentals.get("forward_pe", 0) >= 45:
        conditions.append("Valuation remains elevated while growth expectations weaken.")
    return conditions


def _maybe_llm_analyst(
    state: TradingState,
    node_name: str,
    title: str,
    role_prompt: str,
    data_payload: dict[str, Any],
) -> tuple[Report | None, dict[str, Any] | None]:
    if not _llm_enabled(state):
        return None, None
    try:
        result = _invoke_llm(
            state,
            system_prompt=(
                f"{role_prompt} Return a concise analyst report for {state['ticker']}. "
                "Use only the supplied normalized data. This is research support, not financial advice."
            ),
            payload={
                "ticker": state["ticker"],
                "analysis_date": state["analysis_date"],
                **data_payload,
            },
            schema_name="analyst_report",
            schema={
                "type": "object",
                "additionalProperties": False,
                "required": ["signal", "confidence", "summary"],
                "properties": {
                    "signal": {"type": "string", "enum": ["bullish", "neutral", "bearish"]},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "summary": {"type": "string"},
                },
            },
        )
        return _report(
            title,
            str(result["signal"]),
            round(float(result["confidence"]), 3),
            str(result["summary"]),
        ), _llm_trace(node_name, "success", state)
    except Exception as exc:
        raise _llm_error(node_name, exc) from exc


def _maybe_llm_research_debater(
    state: TradingState,
    node_name: str,
    role_prompt: str,
) -> tuple[str | None, dict[str, Any] | None]:
    if not _llm_enabled(state):
        return None, None
    try:
        result = _invoke_llm(
            state,
            system_prompt=(
                f"{role_prompt} Respond as {node_name}. "
                "Write one concise debate argument that can be appended to the investment debate history. "
                "Use only the supplied reports and debate context. This is research support, not financial advice."
            ),
            payload={
                "ticker": state["ticker"],
                "analysis_date": state["analysis_date"],
                "analyst_reports": _analyst_reports(state),
                "existing_investment_debate_state": state.get("investment_debate_state", {}),
            },
            schema_name="investment_debate_argument",
            schema={
                "type": "object",
                "additionalProperties": False,
                "required": ["argument"],
                "properties": {
                    "argument": {"type": "string"},
                },
            },
        )
        return str(result["argument"]), _llm_trace(node_name, "success", state)
    except Exception as exc:
        raise _llm_error(node_name, exc) from exc


def _maybe_llm_risk_debater(
    state: TradingState,
    node_name: str,
    role_prompt: str,
) -> tuple[str | None, dict[str, Any] | None]:
    if not _llm_enabled(state):
        return None, None
    try:
        result = _invoke_llm(
            state,
            system_prompt=(
                f"{role_prompt} Respond as {node_name}. "
                "Write one concise risk debate statement that can be appended to the risk debate history. "
                "This is research support, not financial advice."
            ),
            payload={
                "ticker": state["ticker"],
                "analysis_date": state["analysis_date"],
                "analyst_reports": _analyst_reports(state),
                "investment_plan": state["investment_plan"],
                "trader_investment_plan": state["trader_investment_plan"],
                "existing_risk_debate_state": state.get("risk_debate_state", {}),
            },
            schema_name="risk_debate_view",
            schema={
                "type": "object",
                "additionalProperties": False,
                "required": ["risk_view"],
                "properties": {
                    "risk_view": {"type": "string"},
                },
            },
        )
        return str(result["risk_view"]), _llm_trace(node_name, "success", state)
    except Exception as exc:
        raise _llm_error(node_name, exc) from exc


def _maybe_llm_research_manager(state: TradingState) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    node_name = "research_manager"
    if not _llm_enabled(state):
        return None, None
    try:
        result = _invoke_llm(
            state,
            system_prompt=(
                "You are the research manager in a multi-agent trading research workflow. "
                "Use analyst reports and debate history to create an investment plan. "
                "This is research support, not financial advice."
            ),
            payload={
                "ticker": state["ticker"],
                "analysis_date": state["analysis_date"],
                "analyst_reports": _analyst_reports(state),
                "investment_debate_state": state.get("investment_debate_state", {}),
            },
            schema_name="investment_plan",
            schema={
                "type": "object",
                "additionalProperties": False,
                "required": ["stance", "score", "summary"],
                "properties": {
                    "stance": {"type": "string", "enum": ["bullish", "neutral", "bearish"]},
                    "score": {"type": "number", "minimum": -1, "maximum": 1},
                    "summary": {"type": "string"},
                },
            },
        )
        result["score"] = round(float(result["score"]), 3)
        return result, _llm_trace(node_name, "success", state)
    except Exception as exc:
        raise _llm_error(node_name, exc) from exc


def _maybe_llm_trader(state: TradingState) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    node_name = "trader"
    if not _llm_enabled(state):
        return None, None
    try:
        result = _invoke_llm(
            state,
            system_prompt=(
                "You are the trader in a multi-agent trading workflow. Convert the "
                "research plan and trade preferences into structured single-ticker trade advice. "
                "The advice is consumed by a future portfolio parent graph, so position_size is "
                "a conviction bucket, not a final portfolio weight. Use trade_intent to separate "
                "watch/wait/open/add/reduce/exit intent from the coarse BUY/HOLD/SELL action."
            ),
            payload={
                "ticker": state["ticker"],
                "analysis_date": state["analysis_date"],
                "investment_plan": state["investment_plan"],
                "trade_preferences": state.get("trade_preferences", {}),
            },
            schema_name="trade_advice",
            schema={
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "action",
                    "trade_intent",
                    "position_size",
                    "confidence",
                    "rationale",
                    "expected_return_pct",
                    "expected_risk_pct",
                    "expected_holding_days",
                    "risk_profile",
                    "trading_style",
                    "entry_plan",
                    "add_position_plan",
                    "reduce_position_plan",
                    "stop_loss_plan",
                    "invalidation_conditions",
                ],
                "properties": {
                    "action": {"type": "string", "enum": ["BUY", "HOLD", "SELL"]},
                    "trade_intent": _trade_intent_schema(),
                    "position_size": {"type": "string", "enum": ["none", "small", "medium", "large"]},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "rationale": {"type": "string"},
                    "expected_return_pct": {"type": "number"},
                    "expected_risk_pct": {"type": "number"},
                    "expected_holding_days": {"type": "integer"},
                    "risk_profile": {"type": "string"},
                    "trading_style": {"type": "string"},
                    "entry_plan": _plan_schema(),
                    "add_position_plan": _plan_schema(),
                    "reduce_position_plan": _plan_schema(),
                    "stop_loss_plan": _plan_schema(),
                    "invalidation_conditions": {"type": "array", "items": {"type": "string"}},
                },
            },
        )
        result["confidence"] = round(float(result["confidence"]), 3)
        result["expected_return_pct"] = round(float(result["expected_return_pct"]), 4)
        result["expected_risk_pct"] = round(float(result["expected_risk_pct"]), 4)
        return result, _llm_trace(node_name, "success", state)
    except Exception as exc:
        raise _llm_error(node_name, exc) from exc


def _maybe_llm_portfolio_manager(state: TradingState) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    node_name = "portfolio_manager"
    if not _llm_enabled(state):
        return None, None
    try:
        result = _invoke_llm(
            state,
            system_prompt=(
                "You are the portfolio manager in a multi-agent trading workflow. "
                "Make the final decision after reviewing the trader proposal and risk debate. "
                "Prefer capital preservation when evidence is weak or risk controls are unclear."
            ),
            payload={
                "ticker": state["ticker"],
                "analysis_date": state["analysis_date"],
                "trader_investment_plan": state["trader_investment_plan"],
                "trade_preferences": state.get("trade_preferences", {}),
                "risk_debate_state": state.get("risk_debate_state", {}),
            },
            schema_name="portfolio_decision",
            schema={
                "type": "object",
                "additionalProperties": False,
                "required": ["risk_assessment", "final_trade_decision", "trade_advice"],
                "properties": {
                    "risk_assessment": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["status", "notes"],
                        "properties": {
                            "status": {"type": "string", "enum": ["approved", "rejected"]},
                            "notes": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                    "final_trade_decision": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["action", "position_size", "confidence", "reason"],
                        "properties": {
                            "action": {"type": "string", "enum": ["BUY", "HOLD", "SELL"]},
                            "position_size": {"type": "string", "enum": ["none", "small", "medium", "large"]},
                            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                            "reason": {"type": "string"},
                        },
                    },
                    "trade_advice": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": [
                            "action",
                            "trade_intent",
                            "position_size",
                            "confidence",
                            "rationale",
                            "expected_return_pct",
                            "expected_risk_pct",
                            "expected_holding_days",
                            "risk_profile",
                            "trading_style",
                            "entry_plan",
                            "add_position_plan",
                            "reduce_position_plan",
                            "stop_loss_plan",
                            "invalidation_conditions",
                        ],
                        "properties": {
                            "action": {"type": "string", "enum": ["BUY", "HOLD", "SELL"]},
                            "trade_intent": _trade_intent_schema(),
                            "position_size": {"type": "string", "enum": ["none", "small", "medium", "large"]},
                            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                            "rationale": {"type": "string"},
                            "expected_return_pct": {"type": "number"},
                            "expected_risk_pct": {"type": "number"},
                            "expected_holding_days": {"type": "integer"},
                            "risk_profile": {"type": "string"},
                            "trading_style": {"type": "string"},
                            "entry_plan": _plan_schema(),
                            "add_position_plan": _plan_schema(),
                            "reduce_position_plan": _plan_schema(),
                            "stop_loss_plan": _plan_schema(),
                            "invalidation_conditions": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                },
            },
        )
        result["final_trade_decision"]["confidence"] = round(
            float(result["final_trade_decision"]["confidence"]), 3
        )
        result["trade_advice"]["confidence"] = round(float(result["trade_advice"]["confidence"]), 3)
        result["trade_advice"]["expected_return_pct"] = round(float(result["trade_advice"]["expected_return_pct"]), 4)
        result["trade_advice"]["expected_risk_pct"] = round(float(result["trade_advice"]["expected_risk_pct"]), 4)
        return result, _llm_trace(node_name, "success", state)
    except Exception as exc:
        raise _llm_error(node_name, exc) from exc


def _llm_enabled(state: TradingState) -> bool:
    return bool(state.get("llm_config", {}).get("enabled"))


def _invoke_llm(
    state: TradingState,
    *,
    system_prompt: str,
    payload: dict[str, Any],
    schema_name: str,
    schema: dict[str, Any],
) -> dict[str, Any]:
    adapter = get_llm_adapter(state["llm_config"])
    return adapter.response_wrapper(
        system_prompt=system_prompt,
        payload=payload,
        schema_name=schema_name,
        schema=schema,
    )


def _plan_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["method", "trigger", "fraction"],
        "properties": {
            "method": {"type": "string"},
            "trigger": {"type": "string"},
            "fraction": {"type": "number", "minimum": 0, "maximum": 1},
        },
    }


def _trade_intent_schema() -> dict[str, Any]:
    return {"type": "string", "enum": ["open", "add", "reduce", "exit", "watch", "wait"]}


def _llm_trace(
    node_name: str,
    status: str,
    state: TradingState,
    error: Exception | None = None,
) -> dict[str, Any]:
    trace = {
        "node": node_name,
        "status": status,
        "provider": state.get("llm_config", {}).get("provider"),
        "model": state.get("llm_config", {}).get("model"),
    }
    if error:
        trace["error_type"] = type(error).__name__
        trace["error"] = str(error)[:300]
    return trace


def _llm_error(node_name: str, error: Exception) -> RuntimeError:
    return RuntimeError(
        f"LLM is enabled, but {node_name} failed: "
        f"{type(error).__name__}: {str(error)[:500]}"
    )
