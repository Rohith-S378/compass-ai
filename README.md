# Compass AI

Compass AI helps developers find open-source issues that are genuinely
approachable, understand why they are suitable, and identify a sensible
first investigation path.

It inspects a public GitHub repository, retrieves candidate open issues
(labeled `good first issue` or `help wanted`), evaluates them with a
Groq-hosted language model, and produces a ranked terminal report plus a
machine-readable JSON report.

**The first release is an issue-discovery and explanation tool, not an
autonomous coding agent.** It will not modify repositories, execute
untrusted code, create branches, push commits, or open pull requests.

## Architecture

Compass AI is a LangGraph-based state machine. Each node performs one
discrete step and returns partial state updates that flow into the next
node.

```
                +----------------+
                |   repository   |  validate URL, fetch metadata
                +-------+--------+
                        |
                        v
                +----------------+
                | issue_fetcher  |  paginated open-issue scan
                +-------+--------+
                        |
            +-----------+-----------+
            |           |           |
            v           v           v
      +----------+ +----------+ +----------+
      | issue 1  | | issue 2  | | issue N  |   (parallel fan-out
      | evaluate | | evaluate | | evaluate |    when --parallel)
      +----+-----+ +----+-----+ +----+-----+
           |            |            |
           +------------+------------+
                        |
                        v
                +----------------+
                | quality_filter |  difficulty gate + dedup
                +-------+--------+
                        |
                        v
                +----------------+
                |    ranker      |  deterministic score sort
                +-------+--------+
                        |
                        v
                +----------------+
                |  status_track  |  optional PR/contribution
                +-------+--------+    lookup (--github-user)
                        |
                        v
                +----------------+
                |   reporter     |  terminal table + JSON file
                +----------------+
```

**Key nodes:**

| Node | File | Purpose |
|---|---|---|
| `repository` | `compass/nodes/repository.py` | URL validation, owner/name extraction, metadata fetch |
| `issue_fetcher` | `compass/nodes/issue_fetcher.py` | Paginated issue scan, label filtering, PR exclusion |
| `evaluator` | `compass/nodes/evaluator.py` | LLM assessment (clarity, difficulty, actionability, relevance) |
| `parallel_evaluator` | `compass/nodes/parallel_evaluator.py` | LangGraph `Send` fan-out for concurrent evaluation |
| `quality_filter` | `compass/nodes/quality_filter.py` | Difficulty gate, dedup by issue ID |
| `ranker` | `compass/nodes/reporter.py` | Deterministic weighted score, rank assignment |
| `status_tracker` | `compass/nodes/status_tracker.py` | Optional PR/contribution status per user |
| `reporter` | `compass/nodes/reporter.py` | Terminal rendering + JSON report generation |

## Features

- Repository URL validation and owner/name extraction
- Repository metadata and contribution documentation retrieval
- Paginated open-issue retrieval with pull-request exclusion
- Candidate discovery using `good first issue` or `help wanted` labels
- Candidate deduplication by GitHub issue ID
- Groq-based structured issue assessment
- Pydantic validation of model output
- Deterministic scoring and quality filtering in Python
- Bounded pagination/retrieval loop
- Ranked terminal report and JSON output
- Optional parallel evaluation via LangGraph `Send` fan-out
- Optional PR/contribution status tracking

## Requirements

- Python 3.10+
- A [Groq](https://groq.com/) API key (free tier available)
- Optional: a GitHub token for higher rate limits and contribution tracking

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/compass-ai.git
cd compass-ai

# Create and activate a virtual environment
python -m venv .venv
source .venv/Scripts/activate  # Windows: .\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Copy the example environment file and configure your keys
cp .env.example .env
# Edit .env and add your Groq API key and optional GitHub token
```

## Configuration

All configuration is via environment variables (typically in `.env`):

| Variable | Default | Description |
|---|---|---|
| `GROQ_API_KEY` | (required) | Your Groq API key |
| `GROQ_MODEL` | (required) | Groq model identifier |
| `GITHUB_TOKEN` | (optional) | GitHub token (read-only) |
| `COMPASS_TARGET_ISSUES` | 3 | Number of ranked issues to return |
| `COMPASS_MAX_PAGES` | 3 | Maximum issue pages to scan |
| `COMPASS_MAX_CONCURRENCY` | 3 | Max concurrent evaluation workers |
| `COMPASS_REQUEST_TIMEOUT` | 20 | HTTP request timeout in seconds |
| `COMPASS_MAX_DIFFICULTY` | 3 | Maximum difficulty score allowed |

## Usage

```bash
# Basic usage
python -m compass.main https://github.com/owner/repo

# Target more issues, scan more pages
python -m compass.main https://github.com/owner/repo --target 5 --max-pages 3

# Skip LLM evaluation (discovery-only ranking)
python -m compass.main https://github.com/owner/repo --no-llm

# Enable parallel evaluation
python -m compass.main https://github.com/owner/repo --parallel --concurrency 5

# Track PR/contribution status for a specific user
python -m compass.main https://github.com/owner/repo --github-user myusername

# Save report to a specific path
python -m compass.main https://github.com/owner/repo -o my_report.json

# Verbose logging
python -m compass.main https://github.com/owner/repo -v
```

## CLI Options

| Option | Default | Description |
|---|---|---|
| `repo_url` | (required) | Public GitHub repository URL |
| `--target`, `-t` | 3 | Number of ranked issues to return |
| `--max-pages` | 3 | Maximum issue pages to scan |
| `--max-difficulty` | 3 | Maximum difficulty score allowed |
| `--model` | from env | Groq model override |
| `--no-llm` | false | Skip LLM evaluation |
| `--parallel` | false | Enable parallel evaluation |
| `--concurrency`, `-c` | 3 | Max concurrent evaluation workers |
| `--github-user` | none | Track PR/contribution status |
| `--output`, `-o` | reports/ | JSON report path |
| `--no-color` | false | Disable colored output |
| `--verbose`, `-v` | false | Enable verbose logging |

## Output

Compass AI produces two outputs:

1. **Terminal report** — a ranked table with issue details, scores,
   rationale, missing information, prerequisites, and suggested first
   steps.

2. **JSON report** — saved to `reports/` by default, containing run
   metadata and the full shortlist with all assessment details.

## Security and Privacy

- Secrets belong in environment variables, never source control.
- `.env` is ignored by Git.
- API keys and tokens are never printed or written to reports.
- Issue content and repository files are treated as untrusted prompt
   input — the model is instructed to ignore embedded instructions.
- No repository code is executed.
- No automatic cloning, branching, commits, or pull requests.

## Testing

```bash
# Run all tests
python -m pytest -q

# Run a specific test module
python -m pytest tests/test_github_client.py -q
```

Tests use mocked HTTP responses and mocked LLM calls — no live network
calls in unit tests.

## Limitations

- Only public GitHub repositories are supported.
- LLM assessments are advisory, not objective truth.
- The scoring formula is an initial product heuristic, not scientifically
  validated.
- A repository with no suitable issues produces a valid "none found" report.
- The tool does not modify repositories or open pull requests.
- Issue discovery depends on repository maintainers using `good first
  issue` or `help wanted` labels. Repositories that do not use these labels
  will return zero candidates even if they have beginner-friendly issues.
- The LLM model (`openai/gpt-oss-20b` via Groq free tier) does not support
  tool calling. Evaluation uses plain text completion with JSON parsing.
- Groq free-tier rate limits may cause 429 errors on large runs. The SDK
  retries with backoff, but runs can be slow.
- Contribution tracking (`--github-user`) requires a GitHub token for
  reliable results. Unauthenticated requests are subject to strict rate
  limits.
- The current release is a discovery and explanation tool. It does not
  generate code, create branches, push commits, or open pull requests.

## License

See [LICENSE](LICENSE) for details.