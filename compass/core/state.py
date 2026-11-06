"""LangGraph state for Compass AI."""

from __future__ import annotations

import operator
from typing import Any, Annotated, TypedDict


class CompassState(TypedDict, total=False):
    """The shared state for a single Compass run.
    
    Fields are populated progressively by graph nodes. total=False allows
    nodes to return only the fields they update.
    
    `parallel_results` uses an `operator.add` reducer so that parallel
    workers (via Send) can each append their result, and the framework
    merges them automatically.
    """
    # Input
    repo_url: str
    target_count: int
    max_pages: int
    github_user: str | None
    no_llm: bool
    parallel: bool
    
    # Metadata and context
    owner: str
    repo: str
    repo_metadata: dict[str, Any]
    repo_context: str
    
    # Discovery
    issues: list[dict[str, Any]]
    evaluated_issues: list[dict[str, Any]]
    usable_issues: list[dict[str, Any]]
    seen_issue_ids: set[int]
    
    # Parallel worker results (reducer-appended)
    parallel_results: Annotated[list[dict[str, Any]], operator.add]
    
    # Loop control
    page: int
    attempts: int
    max_attempts: int
    max_difficulty: int
    
    # Results
    final_shortlist: list[dict[str, Any]]
    errors: list[str]
    report_path: str
    contribution_status: dict[str, Any]