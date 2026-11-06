"""LangGraph orchestration for Compass AI.

Supports both sequential and parallel evaluation modes. The `--parallel`
flag switches between them.
"""

from __future__ import annotations
from typing import Any
from langgraph.graph import StateGraph, START, END
from compass.core.state import CompassState
from compass.nodes.repository import repository_inspector
from compass.nodes.issue_fetcher import issue_retriever
from compass.nodes.evaluator import evaluate_candidates
from compass.nodes.quality_filter import quality_filter
from compass.nodes.reporter import ranker, report_generator
from compass.nodes.status_tracker import contribution_status_node
from compass.nodes.parallel_evaluator import (
    route_evaluator,
    evaluate_worker,
    aggregate_parallel_results,
)


def route_after_filter(state: CompassState) -> str:
    """Decide next node after quality filtering.
    
    1. If usable candidates meet target_count, go to ranking.
    2. Otherwise, if the page/attempt limit has not been reached, go to retrieval.
    3. Otherwise, go to ranking with the candidates found so far.
    """
    usable_count = len(state.get("usable_issues", []))
    target = state.get("target_count", 3)
    attempts = state.get("attempts", 0)
    max_attempts = state.get("max_attempts", 3)
    
    if usable_count >= target:
        return "ranker"
    if attempts < max_attempts:
        return "issue_retriever"
    return "ranker"


def build_graph() -> Any:
    """Build and compile the Compass AI LangGraph."""
    graph = StateGraph(CompassState)
    
    # Register nodes
    graph.add_node("repository_inspector", repository_inspector)
    graph.add_node("issue_retriever", issue_retriever)
    graph.add_node("evaluate_candidates", evaluate_candidates)
    graph.add_node("quality_filter", quality_filter)
    graph.add_node("ranker", ranker)
    graph.add_node("report_generator", report_generator)
    graph.add_node("status_tracker", contribution_status_node)
    
    # Parallel mode nodes
    graph.add_node("evaluate_worker", evaluate_worker)
    graph.add_node("aggregate_parallel_results", aggregate_parallel_results)
    
    # Edges
    graph.add_edge(START, "repository_inspector")
    graph.add_edge("repository_inspector", "issue_retriever")
    
    # Choose evaluation mode — parallel fans out via Send, sequential is direct
    graph.add_conditional_edges(
        "issue_retriever",
        route_evaluator,
        ["evaluate_candidates", "evaluate_worker", "aggregate_parallel_results"]
    )
    
    # Sequential path
    graph.add_edge("evaluate_candidates", "quality_filter")
    
    # Parallel path: workers -> aggregate -> filter
    graph.add_edge("evaluate_worker", "aggregate_parallel_results")
    graph.add_edge("aggregate_parallel_results", "quality_filter")
    
    # Conditional router
    graph.add_conditional_edges("quality_filter", route_after_filter, ["ranker", "issue_retriever"])
    
    graph.add_edge("ranker", "status_tracker")
    graph.add_edge("status_tracker", "report_generator")
    graph.add_edge("report_generator", END)
    
    return graph.compile()