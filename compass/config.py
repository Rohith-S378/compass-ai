"""Configuration for Compass AI.

Secrets are read from environment variables (typically loaded from the
project-local ``.env`` file). Values are intentionally optional at import
time so unit tests can import this module without a real API key. The
Groq client is the only place that requires a key, and it is constructed
lazily.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Load .env from the project root if present. Does not override existing
# environment variables, so values set in the shell take precedence.
load_dotenv(PROJECT_ROOT / ".env")


def get_required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(
            f"{name} is missing. Configure it in the project .env file."
        )
    return value


def get_optional_env(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value or None


# --- Secrets (optional at import; required only where actually used) ---------

GROQ_API_KEY: str | None = get_optional_env("GROQ_API_KEY")
GROQ_MODEL: str | None = get_optional_env("GROQ_MODEL")
GITHUB_TOKEN: str | None = get_optional_env("GITHUB_TOKEN")

# --- Runtime tuning ----------------------------------------------------------

TARGET_ISSUES: int = int(os.getenv("COMPASS_TARGET_ISSUES", "3"))
MAX_PAGES: int = int(os.getenv("COMPASS_MAX_PAGES", "3"))
MAX_CONCURRENCY: int = int(os.getenv("COMPASS_MAX_CONCURRENCY", "3"))
REQUEST_TIMEOUT: float = float(os.getenv("COMPASS_REQUEST_TIMEOUT", "20"))
MAX_DIFFICULTY: int = int(os.getenv("COMPASS_MAX_DIFFICULTY", "3"))

# --- Validation --------------------------------------------------------------

if TARGET_ISSUES < 1:
    raise ValueError("COMPASS_TARGET_ISSUES must be at least 1.")
if MAX_PAGES < 1:
    raise ValueError("COMPASS_MAX_PAGES must be at least 1.")
if MAX_CONCURRENCY < 1:
    raise ValueError("COMPASS_MAX_CONCURRENCY must be at least 1.")
if REQUEST_TIMEOUT <= 0:
    raise ValueError("COMPASS_REQUEST_TIMEOUT must be greater than 0.")
if not (1 <= MAX_DIFFICULTY <= 5):
    raise ValueError("COMPASS_MAX_DIFFICULTY must be between 1 and 5.")