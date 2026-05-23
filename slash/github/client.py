from __future__ import annotations

from dataclasses import dataclass

from github import Auth, Github, GithubException
from github.PullRequest import PullRequest
from github.Repository import Repository


@dataclass
class FileContent:
    path: str
    content: str
    sha: str | None
    size: int


class GitHubClient:
    def __init__(
        self,
        token: str,
        allowed_repos: list[str],
        *,
        all_repos: bool = False,
        max_list_repos: int = 200,
    ) -> None:
        self._gh = Github(auth=Auth.Token(token))
        self._all_repos = all_repos
        self._max_list_repos = max_list_repos
        self._allowed = (
            None if all_repos else {r.lower() for r in allowed_repos}
        )
        self._cached_repo_list: list[str] | None = None

    def _repo(self, full_name: str) -> Repository:
        if not self._all_repos:
            key = full_name.lower()
            if key not in self._allowed:
                raise ValueError(
                    f"Repo '{full_name}' is not allowed. Configure GITHUB_REPOS "
                    "or set GITHUB_ALL_REPOS=true.",
                )
        try:
            return self._gh.get_repo(full_name)
        except GithubException as e:
            if e.status == 404:
                raise ValueError(
                    f"Repo '{full_name}' not found or your token cannot access it.",
                ) from e
            raise

    def _discover_repos(self) -> list[str]:
        names: list[str] = []
        for repo in self._gh.get_user().get_repos(type="all"):
            names.append(repo.full_name)
            if len(names) >= self._max_list_repos:
                break
        return sorted(names)

    def list_repos(self) -> list[str]:
        if self._all_repos:
            if self._cached_repo_list is None:
                self._cached_repo_list = self._discover_repos()
            return list(self._cached_repo_list)
        return sorted(self._allowed or [])

    def access_mode(self) -> str:
        if self._all_repos:
            return "all"
        return "allowlist"

    def get_default_branch(self, repo: str) -> str:
        return self._repo(repo).default_branch

    def read_file(self, repo: str, path: str, ref: str | None = None) -> FileContent:
        r = self._repo(repo)
        branch = ref or r.default_branch
        try:
            content_file = r.get_contents(path, ref=branch)
        except GithubException as e:
            if e.status == 404:
                raise FileNotFoundError(f"{path} not found on {branch}") from e
            raise
        if isinstance(content_file, list):
            raise IsADirectoryError(f"{path} is a directory, not a file")
        raw = content_file.decoded_content
        if isinstance(raw, bytes):
            text = raw.decode("utf-8", errors="replace")
        else:
            text = str(raw)
        return FileContent(
            path=path,
            content=text,
            sha=content_file.sha,
            size=content_file.size,
        )

    def list_directory(self, repo: str, path: str = "", ref: str | None = None) -> list[str]:
        r = self._repo(repo)
        branch = ref or r.default_branch
        contents = r.get_contents(path or "", ref=branch)
        if not isinstance(contents, list):
            return [contents.path]
        return sorted(c.path for c in contents)

    def search_code(self, repo: str, query: str, limit: int = 15) -> list[dict]:
        r = self._repo(repo)
        q = f"{query} repo:{r.full_name}"
        results = self._gh.search_code(q)
        out: list[dict] = []
        for i, item in enumerate(results):
            if i >= limit:
                break
            out.append(
                {
                    "path": item.path,
                    "url": item.html_url,
                    "snippet": (item.text_matches[0].fragment if item.text_matches else ""),
                },
            )
        return out

    def get_pull_request(self, repo: str, number: int) -> PullRequest:
        return self._repo(repo).get_pull(number)

    def get_pr_diff_summary(self, repo: str, number: int, max_files: int = 20) -> str:
        pr = self.get_pull_request(repo, number)
        files = list(pr.get_files())[:max_files]
        lines = [
            f"PR #{number}: {pr.title}",
            f"State: {pr.state} | {pr.html_url}",
            f"Base: {pr.base.ref} <- Head: {pr.head.ref}",
            f"Changed files ({len(files)} shown):",
        ]
        for f in files:
            lines.append(f"  - {f.filename} (+{f.additions}/-{f.deletions})")
        if pr.body:
            lines.append(f"\nDescription:\n{pr.body[:2000]}")
        return "\n".join(lines)

    def create_branch(self, repo: str, branch: str, from_ref: str | None = None) -> str:
        r = self._repo(repo)
        base = from_ref or r.default_branch
        source = r.get_branch(base)
        ref = f"refs/heads/{branch}"
        r.create_git_ref(ref, source.commit.sha)
        return branch

    def commit_files(
        self,
        repo: str,
        branch: str,
        files: dict[str, str],
        message: str,
    ) -> str:
        r = self._repo(repo)
        for path, content in files.items():
            try:
                existing = r.get_contents(path, ref=branch)
                sha = existing.sha if not isinstance(existing, list) else None
            except GithubException:
                sha = None
            if sha:
                r.update_file(
                    path=path,
                    message=message,
                    content=content,
                    sha=sha,
                    branch=branch,
                )
            else:
                r.create_file(
                    path=path,
                    message=message,
                    content=content,
                    branch=branch,
                )
        return r.get_branch(branch).commit.sha

    def create_pull_request(
        self,
        repo: str,
        title: str,
        body: str,
        head: str,
        base: str | None = None,
    ) -> str:
        r = self._repo(repo)
        base_branch = base or r.default_branch
        pr = r.create_pull(title=title, body=body, head=head, base=base_branch)
        return pr.html_url

    def open_pr_with_changes(
        self,
        repo: str,
        branch_name: str,
        files: dict[str, str],
        title: str,
        body: str,
        base: str | None = None,
    ) -> str:
        r = self._repo(repo)
        base_branch = base or r.default_branch
        try:
            self.create_branch(repo, branch_name, from_ref=base_branch)
        except GithubException as e:
            if "Reference already exists" not in str(e):
                raise
        self.commit_files(repo, branch_name, files, title)
        return self.create_pull_request(repo, title, body, branch_name, base_branch)
