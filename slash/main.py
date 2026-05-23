from __future__ import annotations

import logging
import sys

from slash.config import get_settings
from slash.slack.app import create_slack_app
from slash.validate import validate_settings


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("slack_bolt").setLevel(logging.INFO)
    logging.getLogger("slash").setLevel(logging.INFO)
    try:
        settings = get_settings()
    except Exception as e:
        print(
            "Failed to load config. Copy .env.example to .env and fill in values.",
            file=sys.stderr,
        )
        print(e, file=sys.stderr)
        sys.exit(1)

    try:
        from slash.agent.llm import create_llm_client

        create_llm_client(settings)
    except ValueError as e:
        print(e, file=sys.stderr)
        sys.exit(1)

    if not settings.all_repos_enabled and not settings.repo_allowlist:
        print(
            "Set GITHUB_REPOS=owner/repo (allowlist) or GITHUB_ALL_REPOS=true for full access.",
            file=sys.stderr,
        )
        sys.exit(1)

    config_errors = validate_settings(settings)
    if config_errors:
        print("Configuration problems:", file=sys.stderr)
        for err in config_errors:
            print(f"  • {err}", file=sys.stderr)
        sys.exit(1)

    handler = create_slack_app(settings)
    print("v_slash is running (Socket Mode). Mention the bot in Slack to start.")
    handler.start()


if __name__ == "__main__":
    main()
