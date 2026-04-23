import logging
import time

from openai import OpenAI

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536
MAX_RETRIES = 3
BACKOFF_SECONDS = [1, 2, 4]


def build_embedding_text(metadata: dict) -> str:
    category = metadata.get("category", "")
    colors = " and ".join(metadata.get("colors", []))
    occasion = metadata.get("occasion", "")
    style_tags = ", ".join(metadata.get("style_tags", []))
    caption = metadata.get("caption", "")
    gender = metadata.get("gender", "")
    season = metadata.get("season", "")
    pattern = metadata.get("pattern", "")
    product_display_name = metadata.get("product_display_name", "")

    parts = [
        f"{gender} {category}".strip() if gender else category,
        f"in {colors} colors" if colors else "",
        f"for {occasion} occasion" if occasion else "",
        f"season: {season}" if season else "",
        f"pattern: {pattern}" if pattern else "",
        style_tags if style_tags else "",
        caption if caption else "",
        product_display_name if product_display_name else "",
    ]
    return ". ".join(p for p in parts if p).strip()


def generate_embedding(api_key: str, text: str) -> list[float]:
    client = OpenAI(api_key=api_key)

    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=text,
            )
            vector = response.data[0].embedding
            logger.info(
                "Embedding generated: model=%s dimensions=%d",
                EMBEDDING_MODEL, len(vector),
            )
            return vector

        except Exception as e:
            last_error = e
            logger.warning(
                "Attempt %d/%d: Embedding API error: %s",
                attempt + 1, MAX_RETRIES, e,
            )
            if attempt < MAX_RETRIES - 1:
                time.sleep(BACKOFF_SECONDS[attempt])

    raise RuntimeError(
        f"Embedding generation failed after {MAX_RETRIES} attempts: {last_error}"
    )
