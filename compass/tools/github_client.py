"""GitHub API client.

Handles HTTP/API operations only. Does not contain LangGraph nodes, Groq
prompts, ranking logic, or terminal formatting.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

import httpx

from compass.errors import (
    GitHubNotFoundError,
    GitHubPermissionError,
    GitHubRateLimitError,
    GitHubTransientError,
    InputError,
)

logger = logging.getLogger(__name__)


def parse_repo_url(repo_url: str) -> tuple[str, str]:
    """Parse a GitHub repository URL into (owner, repo).

    Accepts:
    - https://github.com/owner/repo
    - https://github.com/owner/repo/
    - https://github.com/owner/repo.git

    Rejects:
    - Unsupported hosts (not github.com)
    - Missing owner or repo names
    - Malformed URLs
    """
    repo_url = repo_url.strip().rstrip("/")
    
    match = re.match(
        r"^(?:https?://)?github\.com/([^/]+)/([^/]+?)(?:\.git)?$",
        repo_url,
        re.IGNORECASE,
    )
    if not match:
        raise InputError(
            f"Invalid GitHub repository URL: '{repo_url}'. "
            "Must be in the format 'https://github.com/owner/repo'."
        )
    
    return match.group(1), match.group(2)


class GitHubClient:
    """Reusable GitHub REST API client with bounded retries."""

    def __init__(
        self,
        token: str | None = None,
        timeout: float = 20.0,
        max_retries: int = 2,
    ) -> None:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "compass-ai",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"

        self.client = httpx.Client(
            base_url="https://api.github.com",
            headers=headers,
            timeout=timeout,
            follow_redirects=True,
        )
        self.max_retries = max_retries

    def __enter__(self) -> "GitHubClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def close(self) -> None:
        self.client.close()

    def _handle_response(self, response: httpx.Response) -> None:
        """Classify HTTP errors into Compass-specific exceptions."""
        if response.is_success:
            return

        status = response.status_code
        if status == 404:
            raise GitHubNotFoundError(f"Resource not found: {response.url}")
        if status == 403:
            if response.headers.get("x-ratelimit-remaining") == "0":
                reset_time = response.headers.get("x-ratelimit-reset")
                raise GitHubRateLimitError(
                    f"GitHub rate limit exceeded. Reset at: {reset_time}"
                )
            raise GitHubPermissionError(f"Permission denied: {response.url}")
        if status == 429:
            raise GitHubRateLimitError(f"GitHub rate limit (secondary) exceeded.")
        if 500 <= status < 600:
            raise GitHubTransientError(
                f"Transient GitHub error ({status}): {response.url}"
            )
        
        response.raise_for_status()

    def _request_with_retry(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """Execute an HTTP request with bounded retry for transient errors."""
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.request(
                    method, path, params=params
                )
                self._handle_response(response)
                return response
            except GitHubTransientError as exc:
                last_error = exc
                if attempt < self.max_retries:
                    wait = 2 ** attempt
                    logger.warning(
                        "Transient GitHub error on %s %s (attempt %d/%d), retrying in %ds",
                        method, path, attempt + 1, self.max_retries + 1, wait,
                    )
                    time.sleep(wait)
                    continue
                raise
            except (GitHubNotFoundError, GitHubPermissionError, GitHubRateLimitError):
                # Never retry these — they're not transient
                raise
        
        # Should be unreachable, but defensive
        if last_error:
            raise last_error
        raise RuntimeError("Request failed after retries")

    def get_repository(self, owner: str, repo: str) -> dict[str, Any]:
        """Fetch repository metadata."""
        response = self._request_with_retry("GET", f"/repos/{owner}/{repo}")
        return response.json()

    def get_file_text(self, owner: str, repo: str, path: str) -> str | None:
        """Fetch file content as text. Returns None if 404."""
        try:
            response = self.client.get(
                f"/repos/{owner}/{repo}/contents/{path}",
                headers={"Accept": "application/vnd.github.raw"},
            )
            self._handle_response(response)
            return response.text
        except GitHubNotFoundError:
            return None

    def get_issues(
        self,
        owner: str,
        repo: str,
        page: int = 1,
        per_page: int = 100,
        state: str = "open",
    ) -> list[dict[str, Any]]:
        """Fetch one page of issues. Excludes PRs."""
        params = {
            "state": state,
            "page": page,
            "per_page": per_page,
            "sort": "updated",
            "direction": "desc",
        }
        response = self._request_with_retry(
            "GET", f"/repos/{owner}/{repo}/issues", params=params
        )
        
        # GitHub Issues endpoint includes PRs; filter them out locally.
        all_items = response.json()
        issues = [
            item for item in all_items
            if "pull_request" not in item
        ]
        return issues

    def get_open_prs(
        self,
        owner: str,
        repo: str,
        page: int = 1,
        per_page: int = 100,
    ) -> list[dict[str, Any]]:
        """Fetch one page of open pull requests (for status tracking)."""
        params = {
            "state": "open",
            "page": page,
            "per_page": per_page,
            "sort": "updated",
            "direction": "desc",
        }
        response = self._request_with_retry(
            "GET", f"/repos/{owner}/{repo}/pulls", params=params
        )
        return response.json()

    def get_issue_comments(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        page: int = 1,
        per_page: int = 100,
    ) -> list[dict[str, Any]]:
        """Fetch one page of comments on an issue."""
        params = {
            "page": page,
            "per_page": per_page,
            "sort": "created",
            "direction": "asc",
        }
        response = self._request_with_retry(
            "GET",
            f"/repos/{owner}/{repo}/issues/{issue_number}/comments",
            params=params,
        )
        return response.json()