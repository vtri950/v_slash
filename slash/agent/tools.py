from __future__ import annotations

import json
from typing import Any, Callable

from slash.github.client import GitHubClient

ToolHandler = Callable[[dict[str, Any]], str]


def tool_definitions() -> list[dict]:
    return [
        {
            "name": "list_repos",
            "description": (
                "List GitHub repositories you can access "
                "(full account list when GITHUB_ALL_REPOS is enabled, else allowlist)."
            ),
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "read_file",
            "description": "Read a text file from a repo at a path (optionally on a branch/ref).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "owner/name"},
                    "path": {"type": "string"},
                    "ref": {"type": "string", "description": "branch or commit SHA"},
                },
                "required": ["repo", "path"],
            },
        },
        {
            "name": "list_directory",
            "description": "List files and folders at a path in a repo.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "repo": {"type": "string"},
                    "path": {"type": "string", "default": ""},
                    "ref": {"type": "string"},
                },
                "required": ["repo"],
            },
        },
        {
            "name": "search_code",
            "description": "Search code in a repo (GitHub code search syntax).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "repo": {"type": "string"},
                    "query": {"type": "string"},
                },
                "required": ["repo", "query"],
            },
        },
        {
            "name": "get_pull_request",
            "description": "Get summary of a pull request by number.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "repo": {"type": "string"},
                    "number": {"type": "integer"},
                },
                "required": ["repo", "number"],
            },
        },
        {
            "name": "create_pull_request",
            "description": (
                "Create a branch, commit one or more file changes, and open a PR. "
                "files is a map of path -> full new file content."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "repo": {"type": "string"},
                    "branch_name": {
                        "type": "string",
                        "description": "New branch name, e.g. slash/fix-typo",
                    },
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                    "files": {
                        "type": "object",
                        "additionalProperties": {"type": "string"},
                    },
                    "base": {"type": "string", "description": "Target base branch"},
                },
                "required": ["repo", "branch_name", "title", "body", "files"],
            },
        },
    ]


class ToolRouter:
    def __init__(self, github: GitHubClient) -> None:
        self._github = github
        self._handlers: dict[str, ToolHandler] = {
            "list_repos": self._list_repos,
            "read_file": self._read_file,
            "list_directory": self._list_directory,
            "search_code": self._search_code,
            "get_pull_request": self._get_pull_request,
            "create_pull_request": self._create_pull_request,
        }

    def run(self, name: str, inputs: dict[str, Any]) -> str:
        handler = self._handlers.get(name)
        if not handler:
            return json.dumps({"error": f"Unknown tool: {name}"})
        try:
            return handler(inputs)
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _list_repos(self, _: dict) -> str:
        return json.dumps({"repos": self._github.list_repos()})

    def _read_file(self, inputs: dict) -> str:
        fc = self._github.read_file(
            inputs["repo"],
            inputs["path"],
            inputs.get("ref"),
        )
        content = fc.content
        if len(content) > 30_000:
            content = content[:30_000] + "\n... [truncated]"
        return json.dumps(
            {"path": fc.path, "size": fc.size, "content": content},
        )

    def _list_directory(self, inputs: dict) -> str:
        entries = self._github.list_directory(
            inputs["repo"],
            inputs.get("path", ""),
            inputs.get("ref"),
        )
        return json.dumps({"entries": entries})

    def _search_code(self, inputs: dict) -> str:
        hits = self._github.search_code(inputs["repo"], inputs["query"])
        return json.dumps({"results": hits})

    def _get_pull_request(self, inputs: dict) -> str:
        summary = self._github.get_pr_diff_summary(
            inputs["repo"],
            int(inputs["number"]),
        )
        return json.dumps({"summary": summary})

    def _create_pull_request(self, inputs: dict) -> str:
        url = self._github.open_pr_with_changes(
            repo=inputs["repo"],
            branch_name=inputs["branch_name"],
            files=inputs["files"],
            title=inputs["title"],
            body=inputs["body"],
            base=inputs.get("base"),
        )
        return json.dumps({"pr_url": url})
