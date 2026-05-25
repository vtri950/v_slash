from __future__ import annotations

import logging
from typing import Any

from anthropic import APIStatusError

from slash.agent.errors import format_llm_error
from slash.agent.llm import create_llm_client
from slash.agent.prompts import SYSTEM_PROMPT, build_user_context
from slash.agent.tools import ToolRouter, tool_definitions
from slash.config import Settings
from slash.github.client import GitHubClient

logger = logging.getLogger(__name__)


class Agent:
    def __init__(self, settings: Settings, github: GitHubClient) -> None:
        self._settings = settings
        self._tools = ToolRouter(github)
        self._client = create_llm_client(settings)

    def run(self, thread_text: str, repo_context: str) -> str:
        user_content = build_user_context(repo_context, thread_text)
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": user_content},
        ]
        tools = tool_definitions()

        for turn in range(self._settings.agent_max_turns):
            try:
                response = self._client.messages.create(
                    model=self._settings.agent_model,
                    max_tokens=8096,
                    system=SYSTEM_PROMPT,
                    tools=tools,
                    messages=messages,
                )
            except APIStatusError as e:
                friendly = format_llm_error(e)
                if friendly:
                    return friendly
                raise

            if response.stop_reason == "end_turn":
                return self._text_from_blocks(response.content)

            if response.stop_reason != "tool_use":
                return self._text_from_blocks(response.content) or (
                    "I couldn't finish that request. Try rephrasing."
                )

            messages.append({"role": "assistant", "content": response.content})

            tool_results: list[dict[str, Any]] = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                logger.info("Tool %s(%s)", block.name, block.input)
                result = self._tools.run(block.name, block.input)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    },
                )

            messages.append({"role": "user", "content": tool_results})

        return (
            "I hit the step limit while working on this. "
            "Try a smaller task or ask me to continue from where I left off."
        )

    @staticmethod
    def _text_from_blocks(blocks: list[Any]) -> str:
        parts = [b.text for b in blocks if hasattr(b, "text") and b.type == "text"]
        return "\n".join(parts).strip()
