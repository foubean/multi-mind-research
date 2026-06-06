from __future__ import annotations

from typing import Any

from mini_trading_agents.llm_adapter.openai import OpenAIAdapter


_ADAPTER_CACHE: dict[tuple[tuple[str, Any], ...], OpenAIAdapter] = {}


def get_llm_adapter(llm_config: dict[str, Any]):
    if not llm_config.get("enabled"):
        raise RuntimeError("LLM is disabled.")

    provider = str(llm_config.get("provider", "openai")).lower()
    cache_key = tuple(sorted(llm_config.items()))
    if cache_key in _ADAPTER_CACHE:
        return _ADAPTER_CACHE[cache_key]

    if provider == OpenAIAdapter.provider:
        adapter = OpenAIAdapter.from_config(llm_config)
    else:
        raise RuntimeError(f"Unsupported LLM provider: {provider}")

    _ADAPTER_CACHE[cache_key] = adapter
    return adapter
