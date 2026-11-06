"""Parallel issue evaluation using LangGraph Send.

Fans out one worker invocation per candidate issue via a conditional edge.
Each worker receives a small input containing its issue and the repository
context it needs. Results are aggregated with deduplication by issue ID.
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.types import Send

from compass.core.state import CompassState
from compass.nodes.evaluator import IssueEvaluation, calculate_score, is_usable

logger = logging.getLogger(__name__)


def route_evaluator(state: CompassState) -> list[Send] | str:
    """Choose between parallel and sequential evaluation.
    
    For parallel mode, returns a list of Send objects — one per candidate
    issue. Each worker receives its issue and the repository context.
    Model configuration is read from env, NOT copied into state.
    """
    if not state.get("parallel"):
        return "evaluate_candidates"
    
    candidates = state.get("issues", [])
    repo_context = state.get("repo_context", "")
    
    if not candidates:
        return "evaluate_candidates"
    
    return [
        Send("evaluate_worker", {
            "issue": issue,
            "repo_context": repo_context,
        })
        for issue in candidates
    ]


def evaluate_worker(state: dict[str, Any]) -> dict[str, Any]:
    """Single-issue evaluation worker."""
    issue = state["issue"]
    repo_context = state["repo_context"]
    
    from compass import config
    from compass.tools.llm import build_llm
    from compass.nodes.evaluator import evaluate_issue
    
    llm = build_llm(config.GROQ_MODEL, config.GROQ_API_KEY)
    result = evaluate_issue(issue, repo_context, llm)
    
    return {"parallel_results": [result]}


def aggregate_parallel_results(state: CompassState) -> dict[str, Any]:
    """Aggregate parallel worker results with deduplication by issue ID.
    
    Retried workers may return the same issue twice — deduplicate by issue ID,
    preserving successful results and recording failures.
    """
    results = state.get("parallel_results", [])
    max_difficulty = state.get("max_difficulty", 3)
    
    # Deduplicate by issue ID
    seen_ids: set[int] = set()
    deduped: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    
    for result in results:
        issue_id = result.get("issue_id")
        if issue_id is None:
            continue
        if issue_id in seen_ids:
            continue
        seen_ids.add(issue_id)
        
        if result.get("error"):
            failures.append(result)
        else:
            deduped.append(result)
    
    # Sort deterministically by issue number
    deduped.sort(key=lambda x: x.get("issue_number", 0))
    
    # Apply quality gate
    usable = []
    for r in deduped:
        eval_obj = r.get("evaluation")
        if eval_obj and r.get("usable", False) and is_usable(eval_obj, max_difficulty=max_difficulty):
            usable.append(r)
    
    return {
        "evaluated_issues": deduped,
        "usable_issues": usable,
        "errors": state.get("errors", []) + [
            f"Issue #{r.get('issue_number')} evaluation failed: {r.get('error')}"
            for r in failures
        ]
    }