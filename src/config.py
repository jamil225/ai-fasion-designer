from functools import lru_cache
from pathlib import Path
import tomllib

from pydantic import Field, field_validator, BaseModel
from pydantic_settings import BaseSettings
import yaml


_APPLICATION_CONFIG_PATH = Path(__file__).resolve().parent.parent / "application.toml"
_GUARDRAILS_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "guardrails.yaml"


class InputGuardrailsConfig(BaseModel):
    enabled: bool = True
    openai_moderation: bool = True


class OutputGuardrailsConfig(BaseModel):
    enabled: bool = True


class GuardrailsConfig(BaseModel):
    enabled: bool = True
    input: InputGuardrailsConfig = Field(default_factory=InputGuardrailsConfig)
    output: OutputGuardrailsConfig = Field(default_factory=OutputGuardrailsConfig)

    @classmethod
    def load(cls) -> "GuardrailsConfig":
        """
        Load guardrails configuration from the YAML configuration file.
        
        Returns:
        	GuardrailsConfig: The configured guardrails settings, or default settings when the file is missing or does not contain a top-level ``guardrails`` section.
        """
        if not _GUARDRAILS_CONFIG_PATH.exists():
            return cls()
        with open(_GUARDRAILS_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if data and "guardrails" in data:
                return cls(**data["guardrails"])
            return cls()


def _load_best_match_score_threshold() -> float:
    """
    Load the configured best-match score threshold from the application configuration.
    
    Returns:
        float: The configured threshold, or 0.20 when the configuration file or setting is unavailable.
    """
    if not _APPLICATION_CONFIG_PATH.exists():
        return 0.20

    with _APPLICATION_CONFIG_PATH.open("rb") as config_file:
        config = tomllib.load(config_file)

    search_config = config.get("search", {})
    return float(search_config.get("best_match_score_threshold", 0.20))


class Settings(BaseSettings):
    # Vertex AI settings (replaces direct Gemini API key)
    google_cloud_project: str = ""
    google_cloud_location: str = "us-central1"
    google_genai_use_vertexai: bool = True
    # NOTE: per-task model names below are RESERVED for future per-task/tier routing.
    # Currently DORMANT — all text tasks + the agent use llm_primary_model (see llm_gateway).
    # Vision model (needs multimodal capability) — flash-lite is cheapest
    vision_model_name: str = "gemini-2.5-flash-lite"
    # Merge model (text-only, can use same cheap model)
    merge_model_name: str = "gemini-2.5-flash-lite"
    # Search enrichment agent (query expansion before vector search)
    search_enrichment_model_name: str = "gemini-2.5-flash"
    # Stylist agent (outfit curation from vector results)
    stylist_model_name: str = "gemini-2.5-pro"
    # Image generation model (virtual try-on via Gemini native image output)
    image_generation_model_name: str = "gemini-2.5-flash"
    # LiteLLM sandbox endpoint model (vertex_ai/ prefix keeps calls on ADC + Vertex billing)
    litellm_test_model_name: str = "vertex_ai/gemini-2.5-flash"

    # --- Multi-provider failover (2026-07-13 design) ---
    # Single Vertex HIGH model used for ALL text tasks + the agent (Router prepends vertex_ai/).
    llm_primary_model: str = "gemini-2.5-pro"
    # Single OpenAI failover model for ALL tasks. MUST support tool-calling (agent uses it too).
    # No safe default — set LLM_FALLBACK_MODEL in .env (e.g. gpt-5.6-terra).
    llm_fallback_model: str = ""
    # Master switch. False => Vertex-only (pre-failover behavior).
    llm_fallback_enabled: bool = True
    # LiteLLM Router cooldown: park a deployment for N seconds after allowed_fails failures.
    llm_cooldown_seconds: int = 60
    llm_allowed_fails: int = 3
    # Agent OpenAI fallback reasoning level via the Responses API: none|low|medium|high.
    # The agent fallback uses /v1/responses so reasoning + tool-calling work together
    # (gpt-5.6 reasoning models reject tools on /v1/chat/completions unless effort=none).
    llm_fallback_reasoning_effort: str = "medium"

    # LLM gateway backend selector — "vertex" (default, cheapest via ADC) or "litellm".
    # Global switch: all gateway text calls use this backend. Per-task model names are
    # unchanged (search_enrichment_model_name, stylist_model_name, etc.).
    # superseded for text by the Router; retained.
    llm_backend: str = "vertex"

    # Virtual try-on
    default_model_image_path: str = ""
    tryon_output_dir: str = "generated_tryons"

    # OpenAI (embeddings only)
    openai_api_key: str = ""

    # Pinecone
    pinecone_api_key: str = ""
    pinecone_index_name: str = "fashion-rag"
    pinecone_environment: str = "us-east-1"

    # Application Settings
    app_api_key: str = ""
    image_folder_path: str = ""
    csv_file_path: str = ""
    default_top_k: int = 10
    best_match_score_threshold: float = _load_best_match_score_threshold()
    hq_image_folder_path: str = ""
    kaggle_username: str = ""
    kaggle_key: str = ""
    ingestion_log_csv_path: str = "ingestion_log.csv"

    # Google OAuth
    google_client_id: str = ""
    session_secret: str = ""

    # Admin authorization — restricts destructive operations
    admin_api_key: str = ""
    admin_emails: list[str] = Field(default_factory=list)

    # Agent (v3.0)
    agent_model_name: str = "gemini-2.5-pro"
    agent_recursion_limit: int = 10
    agent_max_ask_user: int = 3
    agent_max_results: int = 5
    agent_max_turns: int = 20
    agent_default_gender: str = "women"
    agent_default_occasion: str = "casual"
    agent_required_search_fields: list[str] = Field(default_factory=lambda: ["gender", "occasion"])

    # LangSmith observability (opt-in — tracing disabled when key is empty)
    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""
    langchain_project: str = "ai-fashion-designer"

    @field_validator("agent_required_search_fields", mode="before")
    @classmethod
    def _parse_required_search_fields(cls, v: object) -> object:
        """Normalize required search fields provided as a comma-separated string.
        
        Parameters:
            v (object): A comma-separated field string or an existing value.
        
        Returns:
            object: A list of trimmed, non-empty field names for string input; otherwise, the original value.
        """
        if isinstance(v, str):
            return [f.strip() for f in v.split(",") if f.strip()]
        return v

    @field_validator("admin_emails", mode="before")
    @classmethod
    def _parse_admin_emails(cls, v: object) -> object:
        if isinstance(v, str):
            return [e.strip() for e in v.split(",") if e.strip()]
        return v

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "populate_by_name": True, "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
