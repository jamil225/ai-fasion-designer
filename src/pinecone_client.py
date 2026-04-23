import logging
import time

from pinecone import Pinecone

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
BACKOFF_SECONDS = [1, 2, 4]

_pinecone_client: Pinecone | None = None
_pinecone_index = None


def init_pinecone(api_key: str, index_name: str) -> None:
    global _pinecone_client, _pinecone_index
    _pinecone_client = Pinecone(api_key=api_key)
    _pinecone_index = _pinecone_client.Index(index_name)
    logger.info("Pinecone initialized: index=%s", index_name)


def get_index():
    if _pinecone_index is None:
        raise RuntimeError("Pinecone not initialized. Call init_pinecone first.")
    return _pinecone_index


def check_connection(api_key: str, index_name: str) -> bool:
    try:
        pc = Pinecone(api_key=api_key)
        index = pc.Index(index_name)
        index.describe_index_stats()
        return True
    except Exception as e:
        logger.warning("Pinecone connection check failed: %s", e)
        return False


def upsert_vector(
    product_id: str,
    vector: list[float],
    metadata: dict,
) -> None:
    index = get_index()

    # Pinecone metadata must be flat: strings, numbers, booleans, or lists of strings
    pinecone_metadata = {
        "product_id": metadata["product_id"],
        "image_path": metadata["image_path"],
        "file_hash": metadata["file_hash"],
        "category": metadata["category"],
        "colors": metadata["colors"],
        "occasion": metadata["occasion"],
        "style_tags": metadata["style_tags"],
        "caption": metadata["caption"],
        "raw_vision_output": metadata["raw_vision_output"],
        "model_version": metadata["model_version"],
        "ingested_at": metadata["ingested_at"],
        # Enriched fields from vendor CSV
        "gender": metadata.get("gender", ""),
        "product_display_name": metadata.get("product_display_name", ""),
        "season": metadata.get("season", ""),
    }

    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            index.upsert(vectors=[(product_id, vector, pinecone_metadata)])
            logger.info("Upserted product_id=%s to Pinecone", product_id)
            return
        except Exception as e:
            last_error = e
            logger.warning(
                "Attempt %d/%d: Pinecone upsert error for %s: %s",
                attempt + 1, MAX_RETRIES, product_id, e,
            )
            if attempt < MAX_RETRIES - 1:
                time.sleep(BACKOFF_SECONDS[attempt])

    raise RuntimeError(
        f"Pinecone upsert failed after {MAX_RETRIES} attempts for "
        f"{product_id}: {last_error}"
    )


def query_vectors(
    vector: list[float],
    top_k: int = 10,
    filters: dict | None = None,
) -> list[dict]:
    index = get_index()

    query_params: dict = {
        "vector": vector,
        "top_k": top_k,
        "include_metadata": True,
    }
    if filters:
        query_params["filter"] = filters

    response = index.query(**query_params)

    results = []
    for match in response.matches:
        result = {
            "product_id": match.metadata.get("product_id", match.id),
            "image_path": match.metadata.get("image_path", ""),
            "score": match.score,
            "category": match.metadata.get("category", ""),
            "colors": match.metadata.get("colors", []),
            "occasion": match.metadata.get("occasion", ""),
            "style_tags": match.metadata.get("style_tags", []),
            "caption": match.metadata.get("caption", ""),
        }
        results.append(result)

    return results


def delete_all_vectors() -> None:
    """Delete all vectors from the Pinecone index."""
    index = get_index()
    index.delete(delete_all=True)
    logger.info("Deleted all vectors from Pinecone index")


def hash_exists(file_hash: str) -> bool:
    """Check if a file_hash already exists in Pinecone by querying metadata."""
    index = get_index()
    try:
        # Use a dummy zero vector to query with metadata filter
        # We only care about the filter match, not similarity
        response = index.query(
            vector=[0.0] * 1536,
            top_k=1,
            filter={"file_hash": {"$eq": file_hash}},
            include_metadata=False,
        )
        return len(response.matches) > 0
    except Exception as e:
        logger.warning("Hash existence check failed: %s", e)
        return False
