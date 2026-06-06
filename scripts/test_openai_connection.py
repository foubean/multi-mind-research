from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - for Python < 3.11
    import tomli as tomllib


def main() -> None:
    parser = argparse.ArgumentParser(description="Test OpenAI Responses API connectivity.")
    parser.add_argument("--config", default="config.toml", help="TOML config path.")
    parser.add_argument("--model", help="Override model name.")
    parser.add_argument("--base-url", help="Override OpenAI-compatible base URL.")
    parser.add_argument("--api-key-env", default=None, help="Environment variable containing the API key.")
    args = parser.parse_args()

    config = _load_config(args.config)
    llm_config = _resolve_llm_config(config)

    model = args.model or llm_config["model"]
    base_url = args.base_url if args.base_url is not None else llm_config.get("base_url", "")
    api_key_env = args.api_key_env or llm_config.get("api_key_env", "OPENAI_API_KEY")
    api_key = os.getenv(api_key_env)
    if not model:
        raise SystemExit("Missing model. Set [llm].model or pass --model.")
    if not api_key:
        raise SystemExit(f"Missing API key environment variable: {api_key_env}")

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise SystemExit("Install dependencies first: python -m pip install -r requirements.txt") from exc

    client_kwargs: dict[str, Any] = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url

    client = OpenAI(**client_kwargs)
    try:
        response = client.responses.create(
            model=model,
            input="Return exactly: pong",
            max_output_tokens=16,
        )
    except Exception as exc:
        print("OpenAI connection FAILED")
        print(f"model: {model}")
        print(f"base_url: {base_url or 'OpenAI default'}")
        print(f"error_type: {type(exc).__name__}")
        print(f"error: {exc}")
        proxy_envs = [name for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY") if os.getenv(name)]
        if proxy_envs:
            print(f"proxy_envs_set: {', '.join(proxy_envs)}")
        raise SystemExit(1) from exc

    print("OpenAI connection OK")
    print(f"model: {model}")
    print(f"base_url: {base_url or 'OpenAI default'}")
    print(f"output: {response.output_text}")


def _load_config(path: str) -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.exists():
        return {}
    with config_path.open("rb") as config_file:
        return tomllib.load(config_file)


def _resolve_llm_config(config: dict[str, Any]) -> dict[str, Any]:
    if "llm" in config:
        llm = config["llm"]
        return {
            "model": llm.get("model", ""),
            "base_url": llm.get("base_url", ""),
            "api_key_env": llm.get("api_key_env", "OPENAI_API_KEY"),
        }

    provider_name = config.get("model_provider", "OpenAI")
    provider = config.get("model_providers", {}).get(provider_name, {})
    return {
        "model": config.get("model", ""),
        "base_url": provider.get("base_url", ""),
        "api_key_env": provider.get("api_key_env", "OPENAI_API_KEY"),
    }


if __name__ == "__main__":
    main()
