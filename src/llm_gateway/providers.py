"""Provider construction for the LLM gateway.

Two builders — one per engine:
  * build_text_router  -> LiteLLM Router (Vertex primary, OpenAI fallback, cooldown)
  * build_chat_model   -> LangChain chat model (Vertex) with OpenAI fallback for the agent

Functions, not strategy classes (CLAUDE.md §8). No shims (DEC-023): both use the
providers' native mechanisms (LiteLLM Router fallbacks; LangChain with_fallbacks).
"""

from __future__ import annotations

from src.config import Settings

# Router group names (used by gateway.generate_text).
PRIMARY_GROUP = "vertex-high"
FALLBACK_GROUP = "openai-fallback"


def build_text_router(settings: Settings):
    """Build a LiteLLM Router: Vertex-high primary, OpenAI fallback, per-request + cooldown."""
    from litellm import Router

    model_list = [
        {
            "model_name": PRIMARY_GROUP,
            "litellm_params": {
                "model": f"vertex_ai/{settings.llm_primary_model}",
                "vertex_project": settings.google_cloud_project,
                "vertex_location": settings.google_cloud_location,
            },
        }
    ]
    fallbacks: list = []
    if settings.llm_fallback_enabled and settings.llm_fallback_model:
        model_list.append(
            {
                "model_name": FALLBACK_GROUP,
                "litellm_params": {
                    "model": f"openai/{settings.llm_fallback_model}",
                    "api_key": settings.openai_api_key,
                    # gpt-5.6 reasoning models: disable reasoning on the text path too, so
                    # failed-over text calls stay fast/cheap and don't return empty content.
                    "reasoning_effort": "none",
                },
            }
        )
        fallbacks = [{PRIMARY_GROUP: [FALLBACK_GROUP]}]

    return Router(
        model_list=model_list,
        fallbacks=fallbacks,
        allowed_fails=settings.llm_allowed_fails,
        cooldown_time=settings.llm_cooldown_seconds,
        num_retries=3,
    )


def build_chat_model(settings: Settings, *, temperature: float = 0):
    """Build the agent chat model: Vertex primary with a native OpenAI fallback chain."""
    from langchain_google_genai import ChatGoogleGenerativeAI

    base = ChatGoogleGenerativeAI(
        model=settings.llm_primary_model,
        vertexai=settings.google_genai_use_vertexai,
        project=settings.google_cloud_project,
        location=settings.google_cloud_location,
        temperature=temperature,
    )
    if not settings.llm_fallback_enabled or not settings.llm_fallback_model:
        return base

    from langchain_openai import ChatOpenAI

    # reasoning_effort="none" is required for function/tool calling on the GPT-5.6
    # reasoning models via /v1/chat/completions (OpenAI rejects tools otherwise).
    # The agent binds tools, so this keeps the fallback tool-callable. Harmless if the
    # model is later swapped for a non-reasoning one that ignores the param.
    fallback = ChatOpenAI(
        model=settings.llm_fallback_model,
        api_key=settings.openai_api_key,
        temperature=temperature,
        reasoning_effort="none",
    )
    return base.with_fallbacks([fallback])
