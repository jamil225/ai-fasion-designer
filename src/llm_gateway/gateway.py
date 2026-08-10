"""LLM gateway facade.

Single place that owns LLM *connectivity*: provider selection (via the global
`llm_backend` setting), retry with exponential backoff, error wrapping, and
metadata-only logging. Business modules call `generate_text` / `get_chat_model` and
never touch a provider SDK directly, so switching backend or model is a config change.

Prompt construction and response parsing stay in the business modules (SRP).
"""

from __future__ import annotations

import logging
import time

from src.config import get_settings
from src.llm_gateway.providers import LiteLLMProvider, LLMProvider, VertexProvider

logger = logging.getLogger(__name__)

# Matches CLAUDE.md §8: 3 retries with exponential backoff (1s, 2s, 4s).
MAX_RETRIES = 3
BACKOFF_SECONDS = [1, 2, 4]

# Registry — add a backend by adding a class + one entry (Open/Closed).
_PROVIDERS: dict[str, LLMProvider] = {
    "vertex": VertexProvider(),
    "litellm": LiteLLMProvider(),
}


class LLMGatewayError(RuntimeError):
    """Raised when all LLM attempts fail.

    Subclasses RuntimeError so existing callers that catch RuntimeError keep working.
    """


def _resolve_provider() -> tuple[str, LLMProvider]:
    """Resolve the configured language model provider.
    
    Returns:
    	(tuple[str, LLMProvider]): The configured backend name and its provider.
    """
    backend = get_settings().llm_backend
    provider = _PROVIDERS.get(backend)
    if provider is None:
        raise LLMGatewayError(
            f"Unknown llm_backend '{backend}'. Valid options: {sorted(_PROVIDERS)}."
        )
    return backend, provider


def generate_text(
    *,
    task: str,
    model: str,
    system_prompt: str,
    user_message: str,
    temperature: float | None = None,
) -> str:
    """Generate text using the configured backend with centralized retries.
    
    Parameters:
        task (str): Caller label included in gateway metadata.
        model (str): Model identifier.
        system_prompt (str): System instruction for the model.
        user_message (str): User message to process.
        temperature (float | None): Optional sampling temperature.
    
    Returns:
        str: Generated text.
    
    Raises:
        LLMGatewayError: If all configured retry attempts fail.
    """
    backend, provider = _resolve_provider()
    start = time.monotonic()
    last_error: Exception | None = None

    for attempt in range(MAX_RETRIES):
        try:
            text = provider.generate_text(
                model=model,
                system_prompt=system_prompt,
                user_message=user_message,
                temperature=temperature,
            )
            latency_ms = int((time.monotonic() - start) * 1000)
            logger.info(
                "llm_gateway ok — task=%s backend=%s model=%s attempt=%d latency_ms=%d",
                task, backend, model, attempt + 1, latency_ms,
            )
            return text
        except Exception as exc:  # provider-agnostic: wrap any transport failure
            last_error = exc
            logger.warning(
                "llm_gateway retry — task=%s backend=%s model=%s attempt=%d/%d error=%s",
                task, backend, model, attempt + 1, MAX_RETRIES, type(exc).__name__,
            )
            if attempt < MAX_RETRIES - 1:
                time.sleep(BACKOFF_SECONDS[attempt])

    raise LLMGatewayError(
        f"LLM call failed after {MAX_RETRIES} attempts "
        f"(task={task}, backend={backend}, model={model}): {last_error}"
    )


def get_chat_model(*, task: str, model: str, temperature: float = 0):
    """
    Provide the Vertex chat model used by tool-calling agents.
    
    The chat model is always resolved from the Vertex provider, regardless of the configured text-generation backend.
    
    Parameters:
        task (str): Label identifying the agent task.
        model (str): Model name to use.
        temperature (float): Sampling temperature.
    
    Returns:
        BaseChatModel: A Vertex chat model configured for the requested model and temperature.
    """
    configured_backend = get_settings().llm_backend
    if configured_backend != "vertex":
        logger.info(
            "llm_gateway chat model — task=%s: backend=%s configured, but chat is "
            "vertex-pinned (LiteLLM chat deferred)", task, configured_backend,
        )
    logger.info("llm_gateway chat model — task=%s backend=vertex model=%s", task, model)
    return _PROVIDERS["vertex"].get_chat_model(model=model, temperature=temperature)
