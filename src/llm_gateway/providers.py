"""LLM provider strategies.

Each provider implements the same small contract (`LLMProvider`), so adding a new
backend is a new class here — existing providers and the gateway facade stay untouched
(Open/Closed). Providers own ONLY the raw transport to a model; retry/backoff, error
wrapping and logging live in the gateway facade (`gateway.py`).
"""

from __future__ import annotations

from typing import Protocol

from src.config import Settings, get_settings


class LLMProvider(Protocol):
    """Transport contract every backend must satisfy."""

    def generate_text(
        self,
        *,
        model: str,
        system_prompt: str,
        user_message: str,
        temperature: float | None,
    ) -> str: """
        Generate text from a model using system and user prompts.
        
        Parameters:
            model (str): The model identifier.
            system_prompt (str): Instructions that define the model's behavior.
            user_message (str): The user's input.
            temperature (float | None): Sampling temperature, or `None` to use the provider default.
        
        Returns:
            str: The generated text.
        """
        ...

    def get_chat_model(self, *, model: str, temperature: float):
        """
        Rejects requests for an unsupported chat model.
        
        Raises:
            LLMGatewayError: Always, because this provider does not support chat models
                for tool-calling agents.
        """
        ...


class VertexProvider:
    """Google Vertex AI via ADC — the default, cheapest path."""

    def _settings(self) -> Settings:
        """Load the application settings."""
        return get_settings()

    def generate_text(
        self,
        *,
        model: str,
        system_prompt: str,
        user_message: str,
        temperature: float | None,
    ) -> str:
        # Imported lazily so switching to the litellm backend doesn't require google-genai
        # at call time (and vice-versa).
        """
        Generate text using a Google Vertex AI model.
        
        Parameters:
            model (str): The Vertex AI model to use.
            system_prompt (str): Instructions that guide generation.
            user_message (str): The user input to include in the request.
            temperature (float | None): Sampling temperature, or None to use the model default.
        
        Returns:
            str: The generated text.
        """
        from google import genai

        s = self._settings()
        client = genai.Client(
            vertexai=True,
            project=s.google_cloud_project,
            location=s.google_cloud_location,
        )
        # Single concatenated content string — byte-identical to the pre-gateway callers.
        contents = [system_prompt + "\n\n" + user_message]
        config = None
        if temperature is not None:
            from google.genai import types

            config = types.GenerateContentConfig(temperature=temperature)
        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=config,
        )
        return response.text

    def get_chat_model(self, *, model: str, temperature: float):
        """
        Create a LangChain chat model configured for the requested model and Vertex AI settings.
        
        Parameters:
        	model (str): The model identifier.
        	temperature (float): The sampling temperature.
        
        Returns:
        	A configured LangChain chat model.
        """
        from langchain_google_genai import ChatGoogleGenerativeAI

        s = self._settings()
        return ChatGoogleGenerativeAI(
            model=model,
            vertexai=s.google_genai_use_vertexai,
            project=s.google_cloud_project,
            location=s.google_cloud_location,
            temperature=temperature,
        )


class LiteLLMProvider:
    """LiteLLM transport — opt-in for provider-abstraction learning/experiments.

    Text generation routes Gemini through Vertex (ADC, same billing) via the
    `vertex_ai/` model prefix, so per-task config model names stay bare and work for
    both backends. Chat-model construction is intentionally unsupported (see gateway
    scope note): ChatLiteLLM + Vertex Gemini tool-calling has open upstream bugs.
    """

    def _settings(self) -> Settings:
        """Load the application settings."""
        return get_settings()

    def generate_text(
        self,
        *,
        model: str,
        system_prompt: str,
        user_message: str,
        temperature: float | None,
    ) -> str:
        """
        Generate text using the configured LiteLLM model.
        
        Parameters:
            model (str): Model name or provider-qualified model identifier.
            system_prompt (str): Instructions that guide the model's behavior.
            user_message (str): User content sent to the model.
            temperature (float | None): Sampling temperature, or None to use the provider default.
        
        Returns:
            str: Generated text.
        """
        import litellm

        s = self._settings()
        # Bare config names (e.g. "gemini-2.5-flash") become "vertex_ai/gemini-2.5-flash"
        # so LiteLLM uses Vertex + ADC rather than a separate AI Studio key.
        litellm_model = model if "/" in model else f"vertex_ai/{model}"
        kwargs: dict = {
            "model": litellm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "vertex_project": s.google_cloud_project,
            "vertex_location": s.google_cloud_location,
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        response = litellm.completion(**kwargs)
        return response.choices[0].message.content

    def get_chat_model(self, *, model: str, temperature: float):
        # Deferred: ChatLiteLLM + vertex_ai/gemini-* + tool-calling has open 2026 bugs
        # (tool_choice="any" unsupported, null/malformed tool-call responses). The agent
        # stays on Vertex. Import here to avoid a hard dependency at module load.
        """
        Indicates that chat-model access is unavailable for the LiteLLM provider.
        
        Raises:
            LLMGatewayError: Always raised because this provider does not support chat models.
        """
        from src.llm_gateway.gateway import LLMGatewayError

        raise LLMGatewayError(
            "LiteLLM chat model is not supported yet; the agent uses the vertex backend. "
            "Set llm_backend=vertex for agent chat, or use generate_text for text tasks."
        )
