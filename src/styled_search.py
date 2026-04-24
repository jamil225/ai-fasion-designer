import logging
import time

from src.config import Settings
from src.embeddings import generate_embedding
from src.pinecone_client import init_pinecone, query_vectors
from src.query_enrichment import enrich_query
from src.schemas import (
    OutfitCombo,
    QueryEnrichment,
    StandaloneOutfit,
    StyledProductItem,
    StyledSearchRequest,
    StyledSearchResponse,
)
from src.stylist_agent import curate_outfits

logger = logging.getLogger(__name__)


def _build_product_lookup(results: list[dict]) -> dict[str, dict]:
    """Build a product_id → result dict for fast lookup."""
    return {r["product_id"]: r for r in results}


def _result_to_styled_item(result: dict) -> StyledProductItem:
    return StyledProductItem(
        product_id=result["product_id"],
        image_path=result["image_path"],
        category=result["category"],
        colors=result["colors"],
        score=round(result["score"], 4),
        caption=result["caption"],
    )


def run_styled_search(
    settings: Settings,
    request: StyledSearchRequest,
) -> StyledSearchResponse:
    """Orchestrate the two-agent styled search pipeline.

    Flow: enrich query → embed → Pinecone → stylist curation → structured combos.
    """
    start_time = time.time()

    # Initialize Pinecone
    init_pinecone(settings.pinecone_api_key, settings.pinecone_index_name)

    # Step 1: Query enrichment (fallback to original on failure)
    enriched_query = request.query
    try:
        enriched_query = enrich_query(
            api_key=settings.gemini_api_key,
            model_name=settings.search_enrichment_model_name,
            query=request.query,
        )
    except RuntimeError as e:
        logger.warning(
            "Query enrichment failed, using original query: %s", e,
        )

    # Step 2: Generate embedding for the enriched query
    vector = generate_embedding(settings.openai_api_key, enriched_query)

    # Step 3: Vector search — broad retrieval, no filters
    results = query_vectors(vector=vector, top_k=request.top_k)

    # Step 4: Apply score threshold
    results = [
        r for r in results
        if r["score"] >= settings.best_match_score_threshold
    ]

    total_results_from_vector = len(results)
    logger.info(
        "Styled search: %d results after threshold filter (top_k=%d, threshold=%.2f)",
        total_results_from_vector, request.top_k, settings.best_match_score_threshold,
    )

    # Early exit if no results
    if not results:
        elapsed_ms = int((time.time() - start_time) * 1000)
        return StyledSearchResponse(
            combos=[],
            standalone_outfits=[],
            query_enrichment=QueryEnrichment(
                original_query=request.query,
                enriched_query=enriched_query,
            ),
            total_results_from_vector=0,
            latency_ms=elapsed_ms,
        )

    # Step 5: Stylist Agent — curate outfits from results
    stylist_output = curate_outfits(
        api_key=settings.gemini_api_key,
        model_name=settings.stylist_model_name,
        original_query=request.query,
        products=results,
        combo_count=request.combo_count,
    )

    # Step 6: Resolve product_ids back to full metadata
    lookup = _build_product_lookup(results)
    used_ids: set[str] = set()

    combos: list[OutfitCombo] = []
    for raw_combo in stylist_output.get("combos", []):
        top_id = raw_combo.get("top_product_id", "")
        bottom_id = raw_combo.get("bottom_product_id", "")

        # Validate product_ids exist in our results
        if top_id not in lookup:
            logger.warning("Stylist returned unknown top_product_id: %s", top_id)
            continue
        if bottom_id not in lookup:
            logger.warning("Stylist returned unknown bottom_product_id: %s", bottom_id)
            continue

        # Prevent duplicate usage across combos
        if top_id in used_ids or bottom_id in used_ids:
            logger.warning(
                "Stylist reused product_id in multiple combos: top=%s bottom=%s",
                top_id, bottom_id,
            )
            continue

        used_ids.add(top_id)
        used_ids.add(bottom_id)

        combos.append(OutfitCombo(
            combo_rank=raw_combo.get("combo_rank", len(combos) + 1),
            top=_result_to_styled_item(lookup[top_id]),
            bottom=_result_to_styled_item(lookup[bottom_id]),
            styling_rationale=raw_combo.get("styling_rationale", ""),
        ))

    standalone_outfits: list[StandaloneOutfit] = []
    for raw_standalone in stylist_output.get("standalone_outfits", []):
        pid = raw_standalone.get("product_id", "")
        if pid not in lookup:
            logger.warning("Stylist returned unknown standalone product_id: %s", pid)
            continue

        standalone_outfits.append(StandaloneOutfit(
            product_id=lookup[pid]["product_id"],
            image_path=lookup[pid]["image_path"],
            category=lookup[pid]["category"],
            colors=lookup[pid]["colors"],
            score=round(lookup[pid]["score"], 4),
            caption=lookup[pid]["caption"],
            rationale=raw_standalone.get("rationale", ""),
        ))

    elapsed_ms = int((time.time() - start_time) * 1000)

    logger.info(
        "Styled search complete: %d combos, %d standalone, %dms",
        len(combos), len(standalone_outfits), elapsed_ms,
    )

    return StyledSearchResponse(
        combos=combos,
        standalone_outfits=standalone_outfits,
        query_enrichment=QueryEnrichment(
            original_query=request.query,
            enriched_query=enriched_query,
        ),
        total_results_from_vector=total_results_from_vector,
        latency_ms=elapsed_ms,
    )
