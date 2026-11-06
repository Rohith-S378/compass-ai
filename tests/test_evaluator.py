import pytest
from unittest.mock import MagicMock
from compass.nodes.evaluator import IssueEvaluation, calculate_score, is_usable, evaluate_issue

def test_calculate_score():
    eval_obj = IssueEvaluation(
        clarity_score=5,      # 0.3 * 5 = 1.5
        difficulty_score=1,   # 0.25 * (6-1) = 1.25
        actionability_score=5, # 0.25 * 5 = 1.25
        relevance_score=5,    # 0.2 * 5 = 1.0
        suitable_for_beginner=True,
        rationale="test",
        missing_information=[],
        suggested_first_steps=[],
        prerequisites=[]
    )
    # Total = 1.5 + 1.25 + 1.25 + 1.0 = 5.0
    assert calculate_score(eval_obj) == 5.0

def test_is_usable():
    # Perfect candidate
    eval_ok = IssueEvaluation(
        clarity_score=4, difficulty_score=2, actionability_score=4,
        relevance_score=4, suitable_for_beginner=True, rationale="ok",
        missing_information=[], suggested_first_steps=[], prerequisites=[]
    )
    assert is_usable(eval_ok) is True

    # Too difficult
    eval_hard = IssueEvaluation(
        clarity_score=4, difficulty_score=5, actionability_score=4,
        relevance_score=4, suitable_for_beginner=True, rationale="hard",
        missing_information=[], suggested_first_steps=[], prerequisites=[]
    )
    assert is_usable(eval_hard) is False

    # Not for beginners
    eval_not_beg = IssueEvaluation(
        clarity_score=4, difficulty_score=2, actionability_score=4,
        relevance_score=4, suitable_for_beginner=False, rationale="no",
        missing_information=[], suggested_first_steps=[], prerequisites=[]
    )
    assert is_usable(eval_not_beg) is False

def test_evaluate_issue_success():
    llm = MagicMock()
    eval_obj = IssueEvaluation(
        clarity_score=4, difficulty_score=2, actionability_score=4,
        relevance_score=4, suitable_for_beginner=True, rationale="good",
        missing_information=[], suggested_first_steps=[], prerequisites=[]
    )
    # mock plain text completion returning JSON
    response = MagicMock()
    response.content = eval_obj.model_dump_json()
    llm.invoke.return_value = response

    issue = {"id": 123, "number": 1, "title": "test"}
    result = evaluate_issue(issue, "context", llm)

    assert result["issue_id"] == 123
    assert result["evaluation"].clarity_score == 4
    assert result["usable"] is True


def test_evaluate_issue_failure():
    llm = MagicMock()
    llm.invoke.side_effect = Exception("api error")

    issue = {"id": 123, "number": 1}
    result = evaluate_issue(issue, "context", llm)

    assert result["issue_id"] == 123
    assert "error" in result
    assert result["usable"] is False


def test_normalize_payload_aliases_and_types():
    """Model returns non-canonical keys and types; normalization must coerce."""
    from compass.nodes.evaluator import _normalize_payload

    raw = {
        "clarity": "high",        # alias + label string
        "difficulty": 2,
        "actionability": "low",   # alias + label string
        "relevance": 5,
        "suitable_for_beginner": 1,  # integer instead of bool
        "rationale": "ok",
        "missing_information": "step one\nstep two",  # string instead of list
        "suggested_first_steps": ["a", "b"],
        "prerequisites": "x; y",  # string with semicolons
    }
    normalized = _normalize_payload(raw)

    assert normalized["clarity_score"] == 4
    assert normalized["difficulty_score"] == 2
    assert normalized["actionability_score"] == 1
    assert normalized["relevance_score"] == 5
    assert normalized["suitable_for_beginner"] is True
    assert normalized["missing_information"] == ["step one", "step two"]
    assert normalized["suggested_first_steps"] == ["a", "b"]
    assert normalized["prerequisites"] == ["x", "y"]


def test_normalize_payload_clamps_out_of_range():
    """Scores outside 1-5 must be clamped, not rejected."""
    from compass.nodes.evaluator import _normalize_payload

    raw = {
        "clarity_score": 99,
        "difficulty_score": -3,
        "actionability_score": 0,
        "relevance_score": 2,
        "suitable_for_beginner": True,
        "rationale": "x",
        "missing_information": [],
        "suggested_first_steps": [],
        "prerequisites": [],
    }
    normalized = _normalize_payload(raw)
    assert normalized["clarity_score"] == 5
    assert normalized["difficulty_score"] == 1
    assert normalized["actionability_score"] == 1
