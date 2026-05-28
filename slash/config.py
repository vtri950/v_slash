from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _strip_env(value: str) -> str:
    return value.strip().strip('"').strip("'")




class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    slack_bot_token: str
    slack_app_token: str

    github_token: str
    github_repos: str = Field(
        default="",
        description="Comma-separated owner/repo allowlist; use * or set GITHUB_ALL_REPOS=true for all access",
    )
    github_all_repos: bool = False
    github_max_repos_list: int = 200

    deepseek_api_key: Optional[str] = None
    deepseek_base_url: str = "https://api.deepseek.com/anthropic"

    anthropic_api_key: Optional[str] = None

    llm_provider: str = "deepseek"

    agent_max_turns: int = 12
    agent_model: str = "deepseek-v4-flash"

    # PR review reminder
    slack_review_channel: str = Field(
        default="",
        description="Slack channel ID or name to post daily PR review reminders",
    )
    review_reminder_enabled: bool = True
    review_reminder_time: str = Field(
        default="09:00",
        description="Time of day for the reminder in HH:MM (24-hour format)",
    )

    @field_validator(
        "slack_bot_token",
        "slack_app_token",
        "github_token",
        "deepseek_api_key",
        "anthropic_api_key",
        mode="before",
    )
    @classmethod
    def strip_secrets(cls, value: object) -> object:
        if isinstance(value, str):
            return _strip_env(value)
        return value

    @property
    def all_repos_enabled(self) -> bool:
        if self.github_all_repos:
            return True
        return self.github_repos.strip().lower() in ("*", "all")

    @property
    def repo_allowlist(self) -> list[str]:
        if self.all_repos_enabled:
            return []
        return [r.strip() for r in self.github_repos.split(",") if r.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
