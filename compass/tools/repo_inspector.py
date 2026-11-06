"""Repository inspection.

Retrieves selected context files and metadata from a GitHub repository to
provide the LLM with relevant background for issue assessment.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from compass.tools.github_client import GitHubClient

logger = logging.getLogger(__name__)


def inspect_repository(client: GitHubClient, owner: str, repo: str) -> dict[str, Any]:
    """Fetch repository metadata and key context files.

    Retrieves README and contribution documentation to understand project
    goals and setup. Missing optional files are handled gracefully. Excerpts
    are truncated to stay within a reasonable token budget.
    """
    metadata = client.get_repository(owner, repo)
    
    # Selected context files. Order matters for the final context string.
    files_to_check = [
        "README.md",
        "CONTRIBUTING.md",
        "pyproject.toml",
        "requirements.txt",
        "setup.cfg",
    ]
    
    contents: dict[str, str] = {}
    found: list[str] = []
    
    for path in files_to_check:
        text = client.get_file_text(owner, repo, path)
        if text:
            # Truncate large files to ~2000 chars to avoid overwhelming the LLM
            contents[path] = text[:2000] + ("..." if len(text) > 2000 else "")
            found.append(path)

    # Format a compact context string for the LLM
    context_parts = [
        f"Repository: {owner}/{repo}",
        f"Description: {metadata.get('description', 'No description provided')}",
        f"Primary Language: {metadata.get('language', 'Unknown')}",
        f"Stars: {metadata.get('stargazers_count', 0)}",
    ]
    
    for path, text in contents.items():
        context_parts.append(f"\n--- {path} ---\n{text}")

    return {
        "metadata": metadata,
        "context_str": "\n".join(context_parts),
        "files_found": found,
    }