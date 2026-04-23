import logging
import time

from src.embeddings import generate_embedding
from src.pinecone_client import init_pinecone, query_vectors
from src.schemas import (
    MatchedAttributes,
    SearchFilters,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
)

logger = logging.getLogger(__name__)


def _build_pinecone_filters(filters: SearchFilters) -> dict:
    """Convert SearchFilters to Pinecone filter syntax."""
    pinecone_filter: dict = {}

    if filters.colors:
        pinecone_filter["colors"] = {"$in": filters.colors}
    if filters.occasion:
        pinecone_filter["occasion"] = {"$eq": filters.occasion}
    if filters.category:
        pinecone_filter["category"] = {"$in": filters.category}

    return pinecone_filter


def run_search(
    openai_api_key: str,
    pinecone_api_key: str,
    pinecone_index_name: str,
    best_match_score_threshold: float,
    request: SearchRequest,
) -> SearchResponse:
    start_time = time.time()

    # Ensure Pinecone is initialized
    init_pinecone(pinecone_api_key, pinecone_index_name)

    # Step 1: Embed the query text
    query_vector = generate_embedding(openai_api_key, request.query)

    logger.info(
        "Search query='%s' strict_mode=%s top_k=%d threshold=%.2f",
        request.query,
        request.strict_mode,
        request.top_k,
        best_match_score_threshold,
    )

    # Step 2: Build filters for strict mode
    pinecone_filters: dict | None = None
    applied_filters: dict | None = None

    if request.strict_mode and request.filters:
        pinecone_filters = _build_pinecone_filters(request.filters)
        if pinecone_filters:
            applied_filters = {
                k: v for k, v in request.filters.model_dump().items() if v is not None
            }
            logger.info("Strict mode filters: %s", pinecone_filters)

    # Step 3: Query Pinecone
    raw_results = query_vectors(
        vector=query_vector,
        top_k=request.top_k,
        filters=pinecone_filters,
    )

    # Step 4: Format results
    results: list[SearchResultItem] = []
    for item in raw_results:
        if item["score"] <= best_match_score_threshold:
            continue

        results.append(
            SearchResultItem(
                product_id=item["product_id"],
                image_path=item["image_path"],
                score=round(item["score"], 4),
                matched_attributes=MatchedAttributes(
                    colors=item["colors"],
                    occasion=item["occasion"],
                    category=item["category"],
                ),
                caption=item["caption"],
                style_tags=item["style_tags"],
            )
        )

    latency_ms = int((time.time() - start_time) * 1000)

    logger.info(
        "Search completed: query='%s' results=%d latency_ms=%d",
        request.query, len(results), latency_ms,
    )

    if len(results) == 0:
        logger.warning("Zero results for query='%s'", request.query)

    return SearchResponse(
        results=results,
        applied_filters=applied_filters,
        total_results=len(results),
        latency_ms=latency_ms,
    )
