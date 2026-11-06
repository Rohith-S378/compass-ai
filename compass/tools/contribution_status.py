"""Contribution status tracking.

Determines whether a user has contributed to a given issue — e.g. opened
a linked PR or commented. Uses a single bounded PR fetch plus optional
per-issue comment checks.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from compass.tools.github_client import GitHubClient

logger = logging.getLogger(__name__)

# GitHub auto-links issue numbers in PR titles/bodies as #123
_ISSUE_REF_RE = re.compile(r"(?:^|[\s\[\(])#(\d+)(?:[\s\]\)\.,;:]|$)")


def _extract_issue_refs(text: str | None) -> set[int]:
    """Find all issue numbers referenced in text."""
    if not text:
        return set()
    return {int(m) for m in _ISSUE_REF_RE.findall(text)}


def get_contribution_status(
    client: "GitHubClient",
    owner: str,
    repo: str,
    issues: list[dict[str, Any]],
    github_user: str | None = None,
) -> dict[int, dict[str, Any]]:
    """Determine contribution status for each issue.

    Returns a dict mapping issue_number -> status dict with keys:
    - status: "open" | "has_linked_pr" | "user_has_pr" | "user_commented"
    - linked_prs: list of PR numbers that reference this issue
    - user_has_pr: bool (only if github_user provided)
    - user_commented: bool (only if github_user provided)
    """
    result: dict[int, dict[str, Any]] = {
        issue["issue_number"]: {
            "status": "open",
            "linked_prs": [],
            "user_has_pr": False,
            "user_commented": False,
        }
        for issue in issues
    }

    if not issues:
        return result

    # Fetch open PRs once (bounded to first page)
    try:
        prs = client.get_open_prs(owner, repo, page=1, per_page=100)
    except Exception as exc:
        logger.warning("Failed to fetch PRs for status tracking: %s", exc)
        return result

    # Map issue number -> list of PR numbers that reference it
    for pr in prs:
        refs = _extract_issue_refs(pr.get("title", "")) | _extract_issue_refs(
            pr.get("body", "")
        )
        pr_user = (pr.get("user") or {}).get("login", "")
        for issue_num in refs:
            if issue_num in result:
                result[issue_num]["linked_prs"].append(pr.get("number"))
                if github_user and pr_user.lower() == github_user.lower():
                    result[issue_num]["user_has_pr"] = True

    # Optionally check if the user commented on each issue
    if github_user:
        for issue in issues:
            issue_num = issue.get("issue_number")
            if issue_num not in result:
                continue
            try:
                # Fetch comments for this issue (bounded to first page)
                comments = client.get_issue_comments(owner, repo, issue_num)
                for comment in comments:
                    comment_user = (comment.get("user") or {}).get("login", "")
                    if comment_user.lower() == github_user.lower():
                        result[issue_num]["user_commented"] = True
                        break
            except Exception as exc:
                logger.debug(
                    "Failed to check comments for issue #%s: %s", issue_num, exc
                )

    # Set status string based on flags
    for issue_num, info in result.items():
        if info["user_has_pr"]:
            info["status"] = "user_has_pr"
        elif info["user_commented"]:
            info["status"] = "user_commented"
        elif info["linked_prs"]:
            info["status"] = "has_linked_pr"
        else:
            info["status"] = "open"

    return result