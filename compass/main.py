"""Compass AI CLI entry point.

Usage:
    python -m compass.main <repo_url> [options]

Examples:
    python -m compass.main https://github.com/owner/repo
    python -m compass.main https://github.com/owner/repo --target 5 --max-pages 2
    python -m compass.main https://github.com/owner/repo --no-llm
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from typing import Any

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown

from compass import config
from compass.core.graph import build_graph
from compass.errors import LLMConfigurationError
from compass.logging import setup_logging
from compass.tools.llm import verify_model_availability, build_llm


def _sanitize(text: str) -> str:
    """Replace characters the Windows console (cp1252) cannot encode.

    LLM output may contain non-ASCII punctuation (e.g. non-breaking hyphen
    U+2011). On Windows the default codepage is cp1252, which cannot encode
    these characters and raises UnicodeEncodeError. Replace them with ASCII
    equivalents so rendering never crashes.
    """
    if not isinstance(text, str):
        text = str(text)
    return (
        text
        .replace("\u2011", "-")   # non-breaking hyphen
        .replace("\u2013", "-")   # en dash
        .replace("\u2014", "-")   # em dash
        .replace("\u2018", "'")   # left single quote
        .replace("\u2019", "'")   # right single quote
        .replace("\u201c", '"')   # left double quote
        .replace("\u201d", '"')   # right double quote
        .replace("\u2026", "...") # ellipsis
        .replace("\u00a0", " ")   # non-breaking space
    )


console = Console()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="compass.main",
        description="Compass AI - Open-source contribution discovery and repository companion",
    )
    parser.add_argument(
        "repo_url",
        help="Public GitHub repository URL (e.g., https://github.com/owner/repo)",
    )
    parser.add_argument(
        "--target", "-t",
        type=int,
        default=config.TARGET_ISSUES,
        help=f"Number of ranked issues to return (default: {config.TARGET_ISSUES})",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=config.MAX_PAGES,
        help=f"Maximum issue pages to scan (default: {config.MAX_PAGES})",
    )
    parser.add_argument(
        "--max-difficulty",
        type=int,
        default=config.MAX_DIFFICULTY,
        help=f"Maximum difficulty score allowed (default: {config.MAX_DIFFICULTY})",
    )
    parser.add_argument(
        "--model",
        default=config.GROQ_MODEL,
        help="Groq model override (default: from GROQ_MODEL env)",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip LLM evaluation; use discovery-only ranking",
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Enable parallel evaluation (Send fan-out)",
    )
    parser.add_argument(
        "--concurrency", "-c",
        type=int,
        default=config.MAX_CONCURRENCY,
        help=f"Max concurrent evaluation workers (default: {config.MAX_CONCURRENCY})",
    )
    parser.add_argument(
        "--github-user",
        default=None,
        help="GitHub username to track PR/contribution status",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Path to save JSON report (default: reports/)",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    
    setup_logging(verbose=args.verbose)
    
    if args.no_color:
        console.no_color = True
        
    # Build initial state
    initial_state: dict[str, Any] = {
        "repo_url": args.repo_url,
        "target_count": args.target,
        "max_pages": args.max_pages,
        "max_difficulty": args.max_difficulty,
        "github_user": args.github_user,
        "no_llm": args.no_llm,
        "parallel": args.parallel,
        "page": 1,
        "attempts": 0,
        "max_attempts": args.max_pages,
        "model": args.model,
        "output_path": args.output,
        "issues": [],
        "evaluated_issues": [],
        "usable_issues": [],
        "seen_issue_ids": set(),
        "parallel_results": [],
        "final_shortlist": [],
        "errors": [],
    }
    
    # Verify Groq model availability (unless --no-llm)
    if not args.no_llm:
        try:
            verify_model_availability(args.model, config.GROQ_API_KEY)
        except LLMConfigurationError as e:
            console.print(f"[red]Groq configuration error:[/red] {e}")
            return 1
    
    # Build and run graph
    graph = build_graph()
    
    try:
        final_state = graph.invoke(initial_state)
    except Exception as e:
        console.print(f"[red]Fatal error:[/red] {_sanitize(str(e))}")
        return 1
    
    # Display results
    shortlist = final_state.get("final_shortlist", [])
    report_path = final_state.get("report_path", "unknown")
    
    if not shortlist:
        console.print(Panel(
            f"No suitable issues found for [bold]{_sanitize(args.repo_url)}[/bold].\n"
            "Try increasing --max-pages or adjusting --max-difficulty.",
            title="Compass AI",
            border_style="yellow"
        ))
    else:
        console.print(Panel(
            f"Repository: [bold]{_sanitize(args.repo_url)}[/bold]\n"
            f"Found [bold]{len(shortlist)}[/bold] suitable issue(s)",
            title="Compass AI",
            border_style="green"
        ))
        
        table = Table(title="Top Issues")
        table.add_column("Rank", style="cyan", justify="right")
        table.add_column("Issue", style="white")
        table.add_column("Score", style="magenta", justify="right")
        table.add_column("Status", justify="center")
        
        for item in shortlist:
            issue = item.get("issue", {})
            title = _sanitize(issue.get("title", ""))
            table.add_row(
                str(item.get("rank", "?")),
                f"#{item.get('issue_number')} {title}",
                str(item.get("score", "?")),
                item.get("status", "open")
            )
        console.print(table)
        
        # Show details for each issue
        for item in shortlist:
            issue = item.get("issue", {})
            title = _sanitize(issue.get("title", ""))
            eval_obj = item.get("evaluation", {})
            details = f"""
# {item.get('rank')}. #{item.get('issue_number')}: {title}

**URL:** {_sanitize(issue.get('html_url', ''))}

**Scores:**
- Clarity: {eval_obj.clarity_score}/5
- Difficulty: {eval_obj.difficulty_score}/5
- Actionability: {eval_obj.actionability_score}/5
- Relevance: {eval_obj.relevance_score}/5
- **Total:** {item.get('score', '?')}/5

**Rationale:** {_sanitize(eval_obj.rationale)}

**Missing Information:** {', '.join(_sanitize(x) for x in eval_obj.missing_information) or 'None'}

**Prerequisites:** {', '.join(_sanitize(x) for x in eval_obj.prerequisites) or 'None'}

**Suggested First Steps:**
{chr(10).join(f'- {_sanitize(step)}' for step in eval_obj.suggested_first_steps) or '- None'}
"""
            console.print(Markdown(_sanitize(details)))
    
    console.print(f"\n[dim]Report saved to: {report_path}[/dim]")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())