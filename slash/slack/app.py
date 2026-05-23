from __future__ import annotations

import logging
import re
from concurrent.futures import Future, ThreadPoolExecutor

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from slash.agent.errors import format_llm_error
from slash.agent.loop import Agent
from slash.config import Settings
from slash.github.client import GitHubClient
from slash.github.context import repo_context_for_agent

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=2)


def _strip_bot_mention(text: str, bot_user_id: str | None) -> str:
    if not bot_user_id:
        return text.strip()
    return re.sub(rf"<@{re.escape(bot_user_id)}>\s*", "", text).strip()


def _format_thread(messages: list[dict], bot_user_id: str | None) -> str:
    lines: list[str] = []
    for msg in messages:
        user = msg.get("user") or msg.get("bot_id") or "unknown"
        if bot_user_id and user == bot_user_id:
            label = "Slash"
        else:
            label = f"user:{user}"
        text = msg.get("text", "").strip()
        if not text:
            continue
        text = _strip_bot_mention(text, bot_user_id)
        lines.append(f"{label}: {text}")
    return "\n".join(lines)


def _fetch_thread(client: WebClient, channel: str, thread_ts: str) -> list[dict]:
    resp = client.conversations_replies(channel=channel, ts=thread_ts, limit=50)
    return resp.get("messages", [])


def _log_future(future: Future) -> None:
    exc = future.exception()
    if exc is not None:
        logger.exception("Background task failed: %s", exc)


def _post_message(
    client: WebClient,
    channel: str,
    thread_ts: str,
    text: str,
) -> None:
    client.chat_postMessage(
        channel=channel,
        thread_ts=thread_ts,
        text=text[:39000],
    )


def create_slack_app(settings: Settings) -> SocketModeHandler:
    app = App(token=settings.slack_bot_token)
    client = app.client
    github = GitHubClient(
        settings.github_token,
        settings.repo_allowlist,
        all_repos=settings.all_repos_enabled,
        max_list_repos=settings.github_max_repos_list,
    )
    agent = Agent(settings, github)

    auth = client.auth_test()
    bot_user_id: str | None = auth.get("user_id")
    bot_name = auth.get("user", "slash")
    logger.info("Slack bot connected as @%s (id %s)", bot_name, bot_user_id)

    def _run_agent(channel: str, thread_ts: str) -> None:
        try:
            messages = _fetch_thread(client, channel, thread_ts)
            thread_text = _format_thread(messages, bot_user_id)
            repo_context = repo_context_for_agent(settings, github)
            logger.info("Running agent for thread %s in %s", thread_ts, channel)
            answer = agent.run(thread_text, repo_context)
            _post_message(client, channel, thread_ts, answer)
            logger.info("Replied in thread %s", thread_ts)
        except SlackApiError as e:
            err = e.response.get("error", "unknown")
            logger.exception("Slack API error while handling message: %s", err)
            try:
                _post_message(
                    client,
                    channel,
                    thread_ts,
                    f"Slack API error: `{err}`. "
                    "If this is `not_in_channel`, run `/invite @{0}` in the channel.".format(
                        bot_name,
                    ),
                )
            except SlackApiError:
                pass
        except Exception as exc:
            logger.exception("Agent failed")
            friendly = format_llm_error(exc)
            text = friendly or (
                "Something went wrong. Check the terminal running `v-slash` for details."
            )
            try:
                _post_message(client, channel, thread_ts, text)
            except SlackApiError:
                pass

    def _dispatch(channel: str, thread_ts: str, source: str) -> None:
        logger.info("Dispatching %s (channel=%s thread=%s)", source, channel, thread_ts)
        try:
            _post_message(
                client,
                channel,
                thread_ts,
                "On it — reading the thread and checking GitHub…",
            )
        except SlackApiError as e:
            err = e.response.get("error", "unknown")
            logger.error(
                "Cannot post to channel %s: %s — invite the bot: /invite @%s",
                channel,
                err,
                bot_name,
            )
            return
        future = _executor.submit(_run_agent, channel, thread_ts)
        future.add_done_callback(_log_future)

    @app.event("app_mention")
    def on_mention(event, logger):  # noqa: ARG001
        channel = event["channel"]
        thread_ts = event.get("thread_ts") or event["ts"]
        _dispatch(channel, thread_ts, "app_mention")

    @app.event("message")
    def on_message(event, logger):  # noqa: ARG001
        if event.get("subtype") or event.get("bot_id"):
            return

        channel = event["channel"]
        channel_type = event.get("channel_type", "")

        # Direct messages — no @mention required
        if channel_type == "im":
            thread_ts = event.get("thread_ts") or event["ts"]
            _dispatch(channel, thread_ts, "direct_message")
            return

        # Thread reply under a message that @mentioned the bot
        if "thread_ts" not in event:
            return
        thread_ts = event["thread_ts"]
        if thread_ts == event.get("ts"):
            return
        try:
            messages = _fetch_thread(client, channel, thread_ts)
        except SlackApiError:
            return
        if not messages:
            return
        parent_text = messages[0].get("text", "")
        if not bot_user_id or f"<@{bot_user_id}>" not in parent_text:
            return
        _dispatch(channel, thread_ts, "thread_reply")

    @app.error
    def on_bolt_error(error, body, logger):  # noqa: ARG001
        logger.exception("Bolt error: %s body=%s", error, body)

    handler = SocketModeHandler(app, settings.slack_app_token)
    return handler
