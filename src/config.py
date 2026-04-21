from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # External API Keys
    gemini_api_key: str = ""
    openai_api_key: str = ""
    pinecone_api_key: str = ""

    # Pinecone Settings
    pinecone_index_name: str = "fashion-rag"
    pinecone_environment: str = "us-east-1"

    # Application Settings
    app_api_key: str = ""
    image_folder_path: str = ""
    default_top_k: int = 10

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


def get_settings() -> Settings:
    return Settings()
