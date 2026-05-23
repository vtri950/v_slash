from __future__ import annotations

try:
    from anthropic import APIStatusError
except ImportError:
    APIStatusError = None  # type: ignore[misc, assignment]


def format_llm_error(exc: BaseException) -> str | None:
    if APIStatusError is None or not isinstance(exc, APIStatusError):
        return None

    status = exc.status_code
    body = getattr(exc, "body", None) or {}
    message = ""
    if isinstance(body, dict):
        err = body.get("error", {})
        if isinstance(err, dict):
            message = str(err.get("message", ""))

    if status == 402:
        return (
            "DeepSeek returned *402 Insufficient Balance* — your API account has no credits.\n"
            "• Top up: https://platform.deepseek.com/\n"
            "• Or switch provider in `.env`: `LLM_PROVIDER=anthropic` + `ANTHROPIC_API_KEY`"
        )
    if status == 401:
        return (
            "LLM API returned *401 Unauthorized* — check `DEEPSEEK_API_KEY` in `.env`."
        )
    if status == 429:
        return "LLM API rate limit (429). Wait a minute and try again."

    detail = message or str(exc)
    return f"LLM API error ({status}): {detail}"
