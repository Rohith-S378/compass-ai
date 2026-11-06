"""Error taxonomy for Compass AI.

A small set of specific failure types instead of one broad
``except Exception``. Each category maps to a distinct handling policy:

- ``InputError``              -> stop immediately with a clear message.
- ``GitHubNotFoundError``     -> repository or file missing; stop or skip.
- ``GitHubPermissionError``   -> permission denied; never retry as transient.
- ``GitHubRateLimitError``    -> respect reset/retry headers; bounded wait.
- ``GitHubTransientError``    -> bounded exponential backoff.
- ``LLMConfigurationError``   -> misconfigured provider; fail fast.
- ``LLMTransientError``       -> bounded retry.
- ``EvaluationValidationError`` -> invalid structured output; retry once, then fail.
"""

from __future__ import annotations


class CompassError(Exception):
    """Base class for all Compass errors."""


class InputError(CompassError):
    """Invalid user input, e.g. a malformed repository URL."""


class GitHubNotFoundError(CompassError):
    """GitHub returned 404 for a repository or optional file."""


class GitHubPermissionError(CompassError):
    """GitHub returned 403: forbidden or private without permission."""


class GitHubRateLimitError(CompassError):
    """GitHub returned 429: rate limit exceeded."""


class GitHubTransientError(CompassError):
    """Transient GitHub failure (network, 5xx) eligible for backoff retry."""


class LLMConfigurationError(CompassError):
    """Groq is misconfigured or the model is unavailable."""


class LLMTransientError(CompassError):
    """Transient Groq failure (timeout, 5xx) eligible for bounded retry."""


class EvaluationValidationError(CompassError):
    """Model output failed Pydantic validation after retries."""