from __future__ import annotations

from statistics import mean
from typing import Any

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
    ticker = state["ticker"]
    return {
        "market_report": _report(
            "Market/Technical Analyst",
            "bullish",
            0.68,
            f"{ticker} shows constructive momentum with manageable volatility.",
        )
    }


def sentiment_analyst(state: TradingState) -> TradingState:
    ticker = state["ticker"]
    return {
        "sentiment_report": _report(
            "Sentiment Analyst",
            "neutral",
            0.55,
            f"Short-term discussion around {ticker} is active but mixed.",
        )
    }


def news_analyst(state: TradingState) -> TradingState:
    ticker = state["ticker"]
    return {
        "news_report": _report(
            "News Analyst",
            "bullish",
            0.62,
            f"Recent news flow for {ticker} is supportive, with no major negative catalyst.",
        )
    }


def fundamentals_analyst(state: TradingState) -> TradingState:
    ticker = state["ticker"]
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
    argument = "Bull case: " + " ".join(bullish_points)
    debate = _get_debate(state, "investment_debate_state")
    debate["history"].append(argument)
    debate["latest_speaker"] = "bull_researcher"
    debate["count"] += 1
    return {"investment_debate_state": debate}


def bear_researcher(state: TradingState) -> TradingState:
    debate = _get_debate(state, "investment_debate_state")
    argument = (
        "Bear case: sentiment is not decisive, valuation risk remains, and a better "
        "entry point may be needed."
    )
    debate["history"].append(argument)
    debate["latest_speaker"] = "bear_researcher"
    debate["count"] += 1
    return {"investment_debate_state": debate}


def research_manager(state: TradingState) -> TradingState:
    reports = _analyst_reports(state)
    weighted_score = _weighted_signal_score(reports)
    stance = _stance_from_score(weighted_score)
    return {
        "investment_plan": {
            "stance": stance,
            "score": round(weighted_score, 3),
            "summary": (
                "Research conclusion combines analyst evidence with the bull/bear "
                f"debate and recommends a {stance} stance."
            ),
        }
    }


def trader(state: TradingState) -> TradingState:
    plan = state["investment_plan"]
    action = {"bullish": "BUY", "neutral": "HOLD", "bearish": "SELL"}[plan["stance"]]
    position_size = "small" if plan["score"] < 0.45 else "medium"
    return {
        "trader_investment_plan": {
            "action": action,
            "position_size": position_size,
            "confidence": min(0.9, 0.5 + abs(plan["score"]) / 2),
            "rationale": plan["summary"],
        }
    }


def aggressive_risk_debater(state: TradingState) -> TradingState:
    proposal = state["trader_investment_plan"]
    return _append_risk_view(
        state,
        "aggressive_risk_debater",
        f"Aggressive view: accept the {proposal['position_size']} {proposal['action']} plan if momentum persists.",
    )


def neutral_risk_debater(state: TradingState) -> TradingState:
    proposal = state["trader_investment_plan"]
    return _append_risk_view(
        state,
        "neutral_risk_debater",
        f"Neutral view: keep the {proposal['action']} proposal but require clear invalidation criteria.",
    )


def conservative_risk_debater(state: TradingState) -> TradingState:
    proposal = state["trader_investment_plan"]
    return _append_risk_view(
        state,
        "conservative_risk_debater",
        f"Conservative view: cap exposure; {proposal['position_size']} is acceptable only with tight risk control.",
    )


def portfolio_manager(state: TradingState) -> TradingState:
    proposal = state["trader_investment_plan"]
    risk_count = state["risk_debate_state"]["count"]
    approved = proposal["confidence"] >= 0.6 and risk_count >= 3
    action = proposal["action"] if approved else "HOLD"
    position_size = proposal["position_size"] if approved else "none"
    confidence = round(mean([proposal["confidence"], 0.65]), 2)
    return {
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
    }


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
        return existing
    return {"history": [], "latest_speaker": "", "count": 0}


def _append_risk_view(state: TradingState, speaker: str, message: str) -> TradingState:
    debate = _get_debate(state, "risk_debate_state")
    debate["history"].append(message)
    debate["latest_speaker"] = speaker
    debate["count"] += 1
    return {"risk_debate_state": debate}
