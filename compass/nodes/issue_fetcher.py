from __future__ import annotations
from typing import Any
from compass.core.state import CompassState
from compass.tools.github_client import GitHubClient

def _has_target_label(issue: dict[str, Any]) -> bool:
    """Check if an issue has a target discovery label.
    
    Matches case-insensitively and tolerates emoji prefixes (e.g.
    ':beginner: Good first issue' still matches 'good first issue').
    """
    target_labels = {"good first issue", "help wanted"}
    for label in issue.get("labels", []):
        name = (label.get("name") or "").casefold()
        if not name:
            continue
        for target in target_labels:
            if target in name or name in target:
                return True
    return False


def issue_retriever(state: CompassState) -> dict[str, Any]:
    """Fetch one page of issues."""
    page = state.get("page", 1)
    seen_ids = state.get("seen_issue_ids", set())
    
    from compass import config
    with GitHubClient(token=config.GITHUB_TOKEN) as client:
        new_issues = client.get_issues(
            state["owner"], 
            state["repo"], 
            page=page
        )
        
    # Deduplicate and filter candidates (good first issue / help wanted)
    candidates = []
    for issue in new_issues:
        if issue["id"] in seen_ids:
            continue
            
        if _has_target_label(issue):
            candidates.append(issue)
            seen_ids.add(issue["id"])
            
    return {
        "issues": candidates,
        "page": page + 1,
        "attempts": state.get("attempts", 0) + 1,
        "seen_issue_ids": seen_ids
    }
