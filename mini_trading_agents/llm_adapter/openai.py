from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class OpenAIAdapterConfig:
    model: str
    api_key: str = ""
    api_key_env: str = "OPENAI_API_KEY"
    base_url: str = ""
    temperature: float = 0.2


class OpenAIAdapter:
    provider = "openai"

    def __init__(self, config: OpenAIAdapterConfig) -> None:
        if not config.model:
            raise RuntimeError("Missing LLM model in config.")
        self.config = config
        self._client = None

    @classmethod
    def from_config(cls, llm_config: dict[str, Any]) -> "OpenAIAdapter":
        provider = str(llm_config.get("provider", "openai")).lower()
        if provider != cls.provider:
            raise RuntimeError(f"Unsupported OpenAI adapter provider: {provider}")
        return cls(
            OpenAIAdapterConfig(
                model=str(llm_config.get("model", "")),
                api_key=str(llm_config.get("api_key", "")),
                api_key_env=str(llm_config.get("api_key_env", "OPENAI_API_KEY")),
                base_url=str(llm_config.get("base_url", "")),
                temperature=float(llm_config.get("temperature", 0.2)),
            )
        )

    def response_wrapper(
        self,
        *,
        system_prompt: str,
        payload: dict[str, Any],
        schema_name: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        response = self.client.responses.create(
            model=self.config.model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=2)},
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "schema": schema,
                    "strict": True,
                }
            },
            temperature=self.config.temperature,
        )
        return json.loads(response.output_text)

    def check_connection(self) -> str:
        response = self.client.responses.create(
            model=self.config.model,
            input="Return exactly: pong",
            max_output_tokens=16,
        )
        return response.output_text

    @property
    def client(self):
        if self._client is None:
            self._client = self._build_client()
        return self._client

    def _build_client(self):
        api_key = self.config.api_key or os.getenv(self.config.api_key_env)
        if not api_key:
            raise RuntimeError(f"Missing API key environment variable: {self.config.api_key_env}")

        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - depends on local env
            raise RuntimeError("Install the openai package to enable LLM agents.") from exc

        client_kwargs: dict[str, Any] = {"api_key": api_key}
        if self.config.base_url:
            client_kwargs["base_url"] = self.config.base_url
        return OpenAI(**client_kwargs)
