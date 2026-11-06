from __future__ import annotations
import json
import os
from datetime import datetime
from typing import Any
from compass.core.state import CompassState
from compass.nodes.evaluator import calculate_score

def ranker(state: CompassState) -> dict[str, Any]:
    """Sort usable candidates by score."""
    usable = state.get("usable_issues", [])
    
    # Sort by score descending, then by issue number ascending
    sorted_issues = sorted(
        usable,
        key=lambda x: (-x.get("score", 0), x.get("issue_number", 0))
    )
    
    # Limit to target count and attach rank
    target = state.get("target_count", 3)
    shortlist = sorted_issues[:target]
    for i, item in enumerate(shortlist):
        item["rank"] = i + 1
    
    return {
        "final_shortlist": shortlist
    }

def report_generator(state: CompassState) -> dict[str, Any]:
    """Generate JSON report."""
    shortlist = state.get("final_shortlist", [])
    contribution_status = state.get("contribution_status", {})
    timestamp = datetime.now().isoformat()
    
    report = {
        "run_metadata": {
            "repository_url": state.get("repo_url"),
            "owner": state.get("owner"),
            "repo": state.get("repo"),
            "timestamp": timestamp,
            "model": state.get("model", "unknown"),
            "pages_fetched": state.get("page", 1) - 1,
            "candidates_discovered": len(state.get("issues", [])),
            "evaluated_successfully": len([
                e for e in state.get("evaluated_issues", []) 
                if not e.get("error")
            ]),
            "rejected_or_failed": len([
                e for e in state.get("evaluated_issues", []) 
                if e.get("error")
            ]),
            "shortlist_count": len(shortlist),
            "errors": state.get("errors", [])
        },
        "shortlist": [
            {
                "rank": i + 1,
                "issue_number": item.get("issue_number"),
                "title": item.get("issue", {}).get("title"),
                "url": item.get("issue", {}).get("html_url"),
                "labels": [l.get("name") for l in item.get("issue", {}).get("labels", [])],
                "state": item.get("issue", {}).get("state"),
                "scores": {
                    "clarity": item.get("evaluation", {}).clarity_score,
                    "difficulty": item.get("evaluation", {}).difficulty_score,
                    "actionability": item.get("evaluation", {}).actionability_score,
                    "relevance": item.get("evaluation", {}).relevance_score,
                    "total": item.get("score")
                },
                "suitable_for_beginner": item.get("evaluation", {}).suitable_for_beginner,
                "rationale": item.get("evaluation", {}).rationale,
                "missing_information": item.get("evaluation", {}).missing_information,
                "prerequisites": item.get("evaluation", {}).prerequisites,
                "suggested_first_steps": item.get("evaluation", {}).suggested_first_steps,
                "status": contribution_status.get(
                    item.get("issue_number"),
                    {"status": item.get("issue", {}).get("state", "open")}
                )
            }
            for i, item in enumerate(shortlist)
        ]
    }
    
    # Save report
    output_path = state.get("output_path")
    if output_path:
        # Custom path: use as-is, but ensure parent dir exists
        report_dir = os.path.dirname(os.path.abspath(output_path))
        os.makedirs(report_dir, exist_ok=True)
        report_path = output_path
    else:
        # Default: reports/<owner>_<repo>_<timestamp>.json
        reports_dir = "reports"
        os.makedirs(reports_dir, exist_ok=True)
        filename = f"{state.get('owner', 'unknown')}_{state.get('repo', 'unknown')}_{timestamp.replace(':', '-')}.json"
        report_path = os.path.join(reports_dir, filename)
    
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
        
    return {
        "report_path": report_path
    }