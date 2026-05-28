"""Daily PR review reminder using a self-rescheduling threading.Timer."""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta

from slack_sdk import WebClient

from slash.config import Settings
from slash.github.client import GitHubClient

logger = logging.getLogger(__name__)


def _post_reminder(
    client: WebClient,
    github: GitHubClient,
    settings: Settings,
) -> None:
    """Check open PRs and post a review-reminder message to the configured channel."""
    channel = settings.slack_review_channel
    if not channel:
        logger.info("SLACK_REVIEW_CHANNEL is empty \u2014 skipping reminder")
        return

    prs = github.get_prs_needing_review()
    if not prs:
        logger.info("No PRs needing review today")
        return

    blocks: list[dict] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "\U0001f514 PR Review Reminder"},
        },
        {"type": "divider"},
    ]

    for info in prs:
        if info.pending_reviewers:
            reviewer_text = ", ".join(f"`@{r}`" for r in info.pending_reviewers)
            detail = f"Needs review from: {reviewer_text}"
        else:
            detail = "\u26a0\ufe0f No reviewers assigned \u2014 reviewers needed!"

        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*<{info.url}|{info.repo}#{info.number}>*"
                        f" \u2014 {info.title}\n{detail}"
                    ),
                },
            }
        )

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Generated daily at {now}",
                }
            ],
        }
    )

    try:
        client.chat_postMessage(
            channel=channel,
            blocks=blocks,
            text="PR Review Reminder",
        )
        logger.info("Posted review reminder to %s", channel)
    except Exception:
        logger.exception("Failed to post review reminder to %s", channel)


def _schedule_daily(
    target,
    hour: int,
    minute: int,
    args: tuple,
) -> None:
    """Schedule `target(*args)` to run daily at `hour:minute`."""
    now = datetime.now()
    target_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target_dt <= now:
        target_dt += timedelta(days=1)

    delay = (target_dt - now).total_seconds()

    def wrapper() -> None:
        try:
            target(*args)
        except Exception:
            logger.exception("Daily reminder task failed")
        _schedule_daily(target, hour, minute, args)

    timer = threading.Timer(delay, wrapper)
    timer.daemon = True
    timer.start()
    logger.info(
        "Next PR review reminder scheduled at %s (%d seconds from now)",
        target_dt.strftime("%Y-%m-%d %H:%M"),
        int(delay),
    )


def start_reminder(
    client: WebClient,
    github: GitHubClient,
    settings: Settings,
) -> None:
    """Start the daily PR review reminder loop (no-op if disabled)."""
    if not settings.review_reminder_enabled:
        logger.info("PR review reminder is disabled (REVIEW_REMINDER_ENABLED=false)")
        return

    try:
        hour, minute = map(int, settings.review_reminder_time.split(":"))
    except (ValueError, AttributeError):
        logger.warning(
            "Invalid REVIEW_REMINDER_TIME=%r, defaulting to 09:00",
            settings.review_reminder_time,
        )
        hour, minute = 9, 0

    _schedule_daily(
        _post_reminder,
        hour,
        minute,
        args=(client, github, settings),
    )
    logger.info(
        "PR review reminder enabled \u2014 daily at %02d:%02d in channel %s",
        hour,
        minute,
        settings.slack_review_channel or "(not configured)",
    )
