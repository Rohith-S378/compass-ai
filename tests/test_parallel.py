"""Tests for parallel evaluation."""
import pytest
from unittest.mock import MagicMock, patch
from compass.core.graph import build_graph
from compass.nodes.parallel_evaluator import (
    route_evaluator,
    aggregate_parallel_results,
)
from compass.nodes.evaluator import IssueEvaluation


def test_route_evaluator_sequential():
    state = {"parallel": False, "issues": []}
    assert route_evaluator(state) == "evaluate_candidates"


def test_route_evaluator_parallel_no_candidates():
    state = {"parallel": True, "issues": [], "repo_context": ""}
    assert route_evaluator(state) == "evaluate_candidates"


def test_route_evaluator_parallel_with_candidates():
    from langgraph.types import Send
    state = {
        "parallel": True,
        "issues": [
            {"id": 1, "number": 1, "title": "test 1"},
            {"id": 2, "number": 2, "title": "test 2"},
        ],
        "repo_context": "context",
    }
    sends = route_evaluator(state)
    assert isinstance(sends, list)
    assert len(sends) == 2
    assert all(isinstance(s, Send) for s in sends)


def test_aggregate_dedup():
    """Test that duplicate issue IDs are deduplicated."""
    eval_obj = IssueEvaluation(
        clarity_score=4, difficulty_score=2, actionability_score=4,
        relevance_score=4, suitable_for_beginner=True, rationale="good",
        missing_information=[], suggested_first_steps=[], prerequisites=[]
    )
    state = {
        "parallel_results": [
            {"issue_id": 1, "issue_number": 1, "usable": True, "evaluation": eval_obj, "score": 4.0},
            {"issue_id": 1, "issue_number": 1, "usable": True, "evaluation": eval_obj, "score": 4.0},  # duplicate
            {"issue_id": 2, "issue_number": 2, "usable": False, "error": "failed"},
        ],
        "max_difficulty": 3,
        "errors": [],
    }
    result = aggregate_parallel_results(state)
    assert len(result["evaluated_issues"]) == 1
    assert result["evaluated_issues"][0]["issue_id"] == 1
    assert len(result["errors"]) == 1


@patch("compass.nodes.repository.GitHubClient")
@patch("compass.nodes.issue_fetcher.GitHubClient")
@patch("compass.tools.llm.build_llm")
def test_parallel_graph(mock_llm, mock_fetch_client, mock_repo_client):
    """Test the full parallel graph with mocked dependencies."""
    # Mock repository
    mock_repo_instance = MagicMock()
    mock_repo_instance.__enter__.return_value.get_repository.return_value = {"name": "test"}
    mock_repo_instance.__enter__.return_value.get_file_text.return_value = "readme"
    mock_repo_client.return_value = mock_repo_instance
    
    # Mock issue fetcher
    mock_fetch_instance = MagicMock()
    mock_fetch_instance.__enter__.return_value.get_issues.return_value = [
        {"id": 1, "number": 1, "title": "test issue", "labels": [{"name": "good first issue"}], "state": "open", "html_url": "url"}
    ]
    mock_fetch_client.return_value = mock_fetch_instance
    
    # Mock LLM (plain text completion returning JSON)
    mock_eval = IssueEvaluation(
        clarity_score=4, difficulty_score=2, actionability_score=4,
        relevance_score=4, suitable_for_beginner=True, rationale="good",
        missing_information=[], suggested_first_steps=[], prerequisites=[]
    )
    response = MagicMock()
    response.content = mock_eval.model_dump_json()
    mock_llm.return_value.invoke.return_value = response
    
    graph = build_graph()
    initial_state = {
        "repo_url": "https://github.com/owner/repo",
        "target_count": 1,
        "max_pages": 1,
        "max_difficulty": 3,
        "no_llm": False,
        "parallel": True,
        "page": 1,
        "attempts": 0,
        "max_attempts": 1,
        "issues": [],
        "evaluated_issues": [],
        "usable_issues": [],
        "seen_issue_ids": set(),
        "parallel_results": [],
        "final_shortlist": [],
        "errors": [],
    }
    
    final_state = graph.invoke(initial_state)
    assert len(final_state.get("final_shortlist", [])) > 0
    assert final_state.get("report_path") is not None