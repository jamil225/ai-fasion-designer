from functools import lru_cache
from pathlib import Path
import tomllib

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


_APPLICATION_CONFIG_PATH = Path(__file__).resolve().parent.parent / "application.toml"


def _load_best_match_score_threshold() -> float:
    if not _APPLICATION_CONFIG_PATH.exists():
        return 0.20

    with _APPLICATION_CONFIG_PATH.open("rb") as config_file:
        config = tomllib.load(config_file)

    search_config = config.get("search", {})
    return float(search_config.get("best_match_score_threshold", 0.20))


class Settings(BaseSettings):
    # Gemini LLM settings
    gemini_api_key: str = ""
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

    # Google OAuth
    google_client_id: str = ""
    session_secret: str = ""

    # Agent (v3.0)
    agent_model_name: str = "gemini-2.5-flash"
    agent_recursion_limit: int = 10
    agent_max_ask_user: int = 3
    agent_max_results: int = 5
    agent_max_turns: int = 20
    agent_default_gender: str = "women"
    agent_default_occasion: str = "casual"
    agent_required_search_fields: list[str] = Field(default_factory=lambda: ["gender", "occasion"])

    @field_validator("agent_required_search_fields", mode="before")
    @classmethod
    def _parse_required_search_fields(cls, v: object) -> object:
        if isinstance(v, str):
            return [f.strip() for f in v.split(",") if f.strip()]
        return v

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "populate_by_name": True, "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
