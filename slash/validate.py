from __future__ import annotations

from slash.config import Settings

_EXAMPLE_BOT = "xoxb-your-bot-token"
_EXAMPLE_APP = "xapp-your-app-level-token"
_EXAMPLE_DEEPSEEK = "your-deepseek-api-key"


def validate_settings(settings: Settings) -> list[str]:
    errors: list[str] = []

    bot = settings.slack_bot_token.strip()
    if bot == _EXAMPLE_BOT or len(bot) < 40:
        errors.append(
            "SLACK_BOT_TOKEN is still the .env.example placeholder (or too short). "
            "Paste the real Bot User OAuth Token from api.slack.com → Your App → "
            "OAuth & Permissions (starts with xoxb-, usually 50+ characters).",
        )
    elif not bot.startswith("xoxb-"):
        errors.append("SLACK_BOT_TOKEN must start with xoxb- (Bot User OAuth Token, not xapp-).")

    app = settings.slack_app_token.strip()
    if app == _EXAMPLE_APP or len(app) < 40:
        errors.append(
            "SLACK_APP_TOKEN is still the .env.example placeholder (or too short). "
            "Paste the App-Level Token from Basic Information → App-Level Tokens "
            "(starts with xapp-, scope connections:write).",
        )
    elif not app.startswith("xapp-"):
        errors.append("SLACK_APP_TOKEN must start with xapp- (App-Level Token, not xoxb-).")

    gh = settings.github_token.strip()
    if gh in ("ghp_your_personal_access_token", "") or not gh.startswith(
        ("ghp_", "github_pat_"),
    ):
        errors.append(
            "GITHUB_TOKEN must be a real PAT (ghp_... or github_pat_...) from GitHub settings.",
        )

    if settings.llm_provider.lower() == "deepseek":
        key = (settings.deepseek_api_key or "").strip()
        if key == _EXAMPLE_DEEPSEEK or len(key) < 30:
            errors.append(
                "DEEPSEEK_API_KEY is still the .env.example placeholder. "
                "Paste your key from platform.deepseek.com (usually 30+ characters).",
            )

    return errors
