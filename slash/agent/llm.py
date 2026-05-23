from __future__ import annotations

import anthropic

from slash.config import Settings

DEEPSEEK_ANTHROPIC_BASE_URL = "https://api.deepseek.com/anthropic"


def create_llm_client(settings: Settings) -> anthropic.Anthropic:
    provider = settings.llm_provider.lower()

    if provider == "deepseek":
        if not settings.deepseek_api_key:
            raise ValueError("DEEPSEEK_API_KEY is required when LLM_PROVIDER=deepseek")
        return anthropic.Anthropic(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url or DEEPSEEK_ANTHROPIC_BASE_URL,
        )

    if provider == "anthropic":
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic")
        return anthropic.Anthropic(api_key=settings.anthropic_api_key)

    raise ValueError(
        f"Unknown LLM_PROVIDER '{settings.llm_provider}'. Use 'deepseek' or 'anthropic'.",
    )
