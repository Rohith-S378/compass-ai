from __future__ import annotations
from typing import Any
from compass.core.state import CompassState

def quality_filter(state: CompassState) -> dict[str, Any]:
    """Filter evaluated issues to find usable candidates.

    The quality gate is applied here, not at evaluation time, so that
    ``--max-difficulty`` is respected regardless of what the evaluator
    pre-computed. The ``usable`` flag from ``evaluate_issue`` is advisory
    only; this node is authoritative.
    """
    evaluations = state.get("evaluated_issues", [])
    max_difficulty = state.get("max_difficulty", 3)

    usable = []
    for eval_result in evaluations:
        eval_obj = eval_result.get("evaluation")
        if eval_obj is not None:
            # Re-apply the deterministic gate with the state's difficulty cap
            from compass.nodes.evaluator import is_usable
            if is_usable(eval_obj, max_difficulty=max_difficulty):
                usable.append(eval_result)
        elif eval_result.get("skipped_llm"):
            # Discovery-only mode: no evaluation object, accept all
            usable.append(eval_result)

    return {
        "usable_issues": usable
    }