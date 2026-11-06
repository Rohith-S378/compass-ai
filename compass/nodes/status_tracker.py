"""Contribution status tracking node."""

from __future__ import annotations
from typing import Any
from compass.core.state import CompassState
from compass.tools.github_client import GitHubClient
from compass.tools.contribution_status import get_contribution_status


def contribution_status_node(state: CompassState) -> dict[str, Any]:
    """Track PR/contribution status for the shortlist."""
    github_user = state.get("github_user")
    if not github_user:
        return {"contribution_status": {}}
    
    from compass import config
    with GitHubClient(token=config.GITHUB_TOKEN) as client:
        status = get_contribution_status(
            client,
            state["owner"],
            state["repo"],
            state.get("final_shortlist", []),
            github_user=github_user,
        )
    
    return {"contribution_status": status}