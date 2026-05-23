from slash.config import Settings
from slash.github.client import GitHubClient


def repo_context_for_agent(settings: Settings, github: GitHubClient) -> str:
    if settings.all_repos_enabled:
        repos = github.list_repos()
        n = len(repos)
        cap = settings.github_max_repos_list
        if n == 0:
            return (
                "All repositories your GitHub token can access "
                "(none found — check token scopes)."
            )
        if n >= cap:
            sample = ", ".join(repos[:15])
            return (
                f"All repositories your token can access ({n}+ listed, capped at {cap}). "
                f"Examples: {sample}, … — use list_repos for the full list."
            )
        return (
            f"All repositories your token can access ({n} repos): "
            f"{', '.join(repos)}"
        )

    repos = settings.repo_allowlist
    if not repos:
        return "(no repos configured — set GITHUB_REPOS or GITHUB_ALL_REPOS=true)"
    return ", ".join(repos)
