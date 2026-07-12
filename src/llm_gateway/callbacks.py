"""LiteLLM observability: per-call cost logging + LangSmith wiring.

Registered once at gateway init. Cost is logged via the stdlib logging module
(no logging framework, per CLAUDE.md). LangSmith is opt-in: only wired when the
existing LANGCHAIN_TRACING_V2/LANGCHAIN_API_KEY env is present.
"""

from __future__ import annotations

import logging
import os

import litellm

logger = logging.getLogger(__name__)

_REGISTERED = False


def _log_cost(kwargs: dict, completion_response, start_time, end_time) -> None:
    """LiteLLM success callback: log model, tokens, and USD cost for one call."""
    try:
        cost = kwargs.get("response_cost")
        if cost is None:
            cost = litellm.completion_cost(completion_response=completion_response)
        model = kwargs.get("model")
        usage = getattr(completion_response, "usage", None)
        logger.info("llm_cost — model=%s cost_usd=%.6f usage=%s", model, cost or 0.0, usage)
    except Exception as exc:  # cost logging must never break a request
        logger.debug("llm_cost logging skipped: %s", type(exc).__name__)


def register_llm_callbacks() -> None:
    """Idempotently register cost + LangSmith callbacks on the litellm module."""
    global _REGISTERED
    if _REGISTERED:
        return
    callbacks: list = [_log_cost]
    if os.environ.get("LANGCHAIN_TRACING_V2", "").lower() == "true" and os.environ.get(
        "LANGCHAIN_API_KEY"
    ):
        callbacks.append("langsmith")
        logger.info("llm_gateway: LangSmith callback enabled for LiteLLM calls")
    litellm.success_callback = callbacks
    _REGISTERED = True
    logger.info("llm_gateway: cost tracking callback registered")
