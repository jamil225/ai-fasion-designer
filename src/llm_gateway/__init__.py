"""LLM gateway — the single entry point for all text LLM connectivity.

Business modules import from here only:

    from src.llm_gateway import generate_text, get_chat_model, LLMGatewayError
"""

from src.llm_gateway.gateway import (
    LLMGatewayError,
    generate_text,
    get_chat_model,
)

__all__ = ["LLMGatewayError", "generate_text", "get_chat_model"]
