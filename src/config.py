from functools import lru_cache
from pathlib import Path
import tomllib

from pydantic import Field
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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "populate_by_name": True, "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
