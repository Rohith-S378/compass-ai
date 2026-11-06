"""Groq LLM integration.

Single construction point for the chat model, plus a startup check that
verifies the configured model is currently available to the account. This
catches stale model identifiers early with a clear, actionable message
instead of a confusing runtime failure mid-evaluation.
"""

from __future__ import annotations

import logging

from langchain_groq import ChatGroq

from compass.errors import LLMConfigurationError

logger = logging.getLogger(__name__)


def verify_model_availability(model: str, api_key: str) -> None:
    """Verify that ``model`` is available to the configured Groq account.

    Queries the Groq models endpoint directly (via the ``groq`` SDK) and
    raises :class:`LLMConfigurationError` if the model is missing or the
    request fails for a configuration reason. Transient network errors are
    surfaced as configuration errors too, because a model check at startup
    should not silently degrade into a mid-run failure.
    """

    if not model:
        raise LLMConfigurationError(
            "GROQ_MODEL is not set. Configure it in the project .env file."
        )
    if not api_key:
        raise LLMConfigurationError(
            "GROQ_API_KEY is not set. Configure it in the project .env file."
        )

    try:
        from groq import Groq
    except ImportError as exc:  # pragma: no cover - dependency guarantee
        raise LLMConfigurationError(
            "The 'groq' package is not installed. Install langchain-groq."
        ) from exc

    try:
        client = Groq(api_key=api_key)
        models = client.models.list()
        available = {m.id for m in models.data}
    except Exception as exc:
        raise LLMConfigurationError(
            "Could not verify Groq model availability. Check your network "
            "connection, GROQ_API_KEY, and GROQ_MODEL. Underlying error: "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    if model not in available:
        raise LLMConfigurationError(
            f"Configured Groq model '{model}' is not available to this "
            f"account. Available models include: "
            f"{', '.join(sorted(available)) or 'none reported'}."
        )


def build_llm(model: str, api_key: str, temperature: float = 0.0) -> ChatGroq:
    """Construct a low-temperature Groq chat model.

    Timeouts and retries are configured at the call site where the SDK
    supports them. Never log the API key.
    """

    if not api_key:
        raise LLMConfigurationError(
            "GROQ_API_KEY is not set. Configure it in the project .env file."
        )
    if not model:
        raise LLMConfigurationError(
            "GROQ_MODEL is not set. Configure it in the project .env file."
        )

    return ChatGroq(
        model=model,
        api_key=api_key,
        temperature=temperature,
        timeout=30,
        max_retries=2,
    )