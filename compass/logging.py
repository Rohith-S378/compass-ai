"""Structured logging for Compass AI.

Logs are useful for debugging but must never expose secrets, API keys,
tokens, authorization headers, or environment variable values.
"""

from __future__ import annotations

import logging
import re
from typing import Any


# Patterns that indicate sensitive data we should redact
_SECRET_PATTERNS = [
    re.compile(r"(api[_-]?key|token|secret|password|auth)", re.IGNORECASE),
]


def _redact_sensitive(message: str) -> str:
    """Redact sensitive-looking values from log messages."""
    # Redact anything that looks like a key=value with sensitive key names
    for pattern in _SECRET_PATTERNS:
        message = pattern.sub(r"\1=***", message)
    return message


class RedactingFilter(logging.Filter):
    """Filter that redacts sensitive data from log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _redact_sensitive(str(record.msg))
        # Also redact args if they're strings
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: _redact_sensitive(str(v)) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    _redact_sensitive(str(a)) if isinstance(a, str) else a
                    for a in record.args
                )
        return True


def setup_logging(verbose: bool = False) -> None:
    """Configure root logging with secret-redaction."""
    level = logging.DEBUG if verbose else logging.INFO
    
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    ))
    handler.addFilter(RedactingFilter())
    
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)