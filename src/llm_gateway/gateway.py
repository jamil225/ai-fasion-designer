"""LLM gateway facade — single entry point for LLM connectivity.

Text tasks use a LiteLLM Router (Vertex primary, OpenAI fallback, cooldown).
The agent uses a LangChain chat model with a native OpenAI fallback chain.
Callers stay provider-agnostic and pass a task label; the `model` argument is
currently DORMANT (all tasks resolve to the single primary group) — kept so
re-enabling per-task tiers later is a config change, not a caller change.
"""

from __future__ import annotations

import logging
import time

from src.config import get_settings
from src.llm_gateway.callbacks import register_llm_callbacks
from src.llm_gateway.providers import PRIMARY_GROUP, build_chat_model, build_text_router

logger = logging.getLogger(__name__)

_router = None


class LLMGatewayError(RuntimeError):
    """Raised when all LLM attempts (primary + fallback) fail.

    Subclasses RuntimeError so existing callers that catch RuntimeError keep working.
    """


def _get_router():
    """Lazily build + cache the text Router, registering observability callbacks once."""
    global _router
    if _router is None:
        register_llm_callbacks()
        _router = build_text_router(get_settings())
    return _router


def generate_text(
    *,
    task: str,
    model: str,
    system_prompt: str,
    user_message: str,
    temperature: float | None = None,
) -> str:
    """Generate text via the Router (primary + fallback + cooldown owned by LiteLLM).

    `task` is a caller label for logging. `model` is currently dormant (routed to the
    single primary group). Raises LLMGatewayError if primary AND fallback both fail.
    """
    router = _get_router()
    start = time.monotonic()
    kwargs: dict = {
        "model": PRIMARY_GROUP,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    }
    if temperature is not None:
        kwargs["temperature"] = temperature

    try:
        response = router.completion(**kwargs)
    except Exception as exc:  # provider-agnostic: Router already retried + failed over
        raise LLMGatewayError(f"LLM call failed (task={task}): {exc}") from exc

    latency_ms = int((time.monotonic() - start) * 1000)
    used_model = getattr(response, "model", "?")
    logger.info("llm_gateway ok — task=%s model=%s latency_ms=%d", task, used_model, latency_ms)
    return response.choices[0].message.content


def get_chat_model(*, task: str, model: str, temperature: float = 0):
    """Return the agent chat model (Vertex primary + native OpenAI fallback chain).

    `model` is dormant (uses settings.llm_primary_model). Tool-calling is native on
    both providers. Fallback is per-request (no cooldown) — an accepted trade-off.
    """
    logger.info("llm_gateway chat model — task=%s (primary + fallback chain)", task)
    return build_chat_model(get_settings(), temperature=temperature)
