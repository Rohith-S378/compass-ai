"""Tests for the LangGraph orchestration."""
import pytest
from unittest.mock import MagicMock, patch
from compass.core.graph import build_graph, route_after_filter
from compass.core.state import CompassState


def test_route_enough_candidates():
    state = {"usable_issues": [1, 2, 3], "target_count": 3, "attempts": 1, "max_attempts": 3}
    assert route_after_filter(state) == "ranker"


def test_route_more_pages():
    state = {"usable_issues": [1], "target_count": 3, "attempts": 1, "max_attempts": 3}
    assert route_after_filter(state) == "issue_retriever"


def test_route_limit_reached():
    state = {"usable_issues": [1], "target_count": 3, "attempts": 3, "max_attempts": 3}
    assert route_after_filter(state) == "ranker"


def test_route_zero_usable():
    state = {"usable_issues": [], "target_count": 3, "attempts": 0, "max_attempts": 3}
    assert route_after_filter(state) == "issue_retriever"


def test_route_zero_usable_limit():
    state = {"usable_issues": [], "target_count": 3, "attempts": 3, "max_attempts": 3}
    assert route_after_filter(state) == "ranker"


@patch("compass.nodes.repository.GitHubClient")
@patch("compass.nodes.issue_fetcher.GitHubClient")
@patch("compass.tools.llm.build_llm")
def test_graph_happy_path(mock_llm, mock_fetch_client, mock_repo_client):
    """Test the full graph with mocked dependencies."""
    # Mock repository inspector - GitHubClient() returns a context manager
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
    
    # Mock LLM
    from compass.nodes.evaluator import IssueEvaluation
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
        "page": 1,
        "attempts": 0,
        "max_attempts": 1,
        "issues": [],
        "evaluated_issues": [],
        "usable_issues": [],
        "seen_issue_ids": set(),
        "final_shortlist": [],
        "errors": [],
    }
    
    final_state = graph.invoke(initial_state)
    assert len(final_state.get("final_shortlist", [])) > 0
    assert final_state.get("report_path") is not None