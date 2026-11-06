from __future__ import annotations
from typing import Any
from compass.core.state import CompassState
from compass.tools.github_client import GitHubClient, parse_repo_url
from compass.tools.repo_inspector import inspect_repository

def repository_inspector(state: CompassState) -> dict[str, Any]:
    """Inspect the repository and extract context."""
    owner, repo = parse_repo_url(state["repo_url"])
    
    # We'll use a single client instance throughout the run if possible
    # For now, create one per node or pass it in.
    # In a real app, you might inject this via config or a tool.
    from compass import config
    with GitHubClient(token=config.GITHUB_TOKEN) as client:
        result = inspect_repository(client, owner, repo)
        
    return {
        "owner": owner,
        "repo": repo,
        "repo_metadata": result["metadata"],
        "repo_context": result["context_str"]
    }
