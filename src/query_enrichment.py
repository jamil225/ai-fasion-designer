import logging

from src.llm_gateway import generate_text

logger = logging.getLogger(__name__)

QUERY_ENRICHMENT_SYSTEM_PROMPT = """You are a fashion search query expansion specialist. Your job is to take a user's natural language fashion query and expand it into a richer semantic search query that will match well against a fashion product database.

The product database contains garments described in this format:
"{gender} {category}. in {colors} colors. for {occasion} occasion. season: {season}. pattern: {pattern}. {style_tags}. {caption}. {product_display_name}"

Your expanded query should:
1. Infer implicit attributes the user likely wants but didn't state explicitly
2. Add synonymous terms and related fashion vocabulary
3. Expand color references (e.g. "earth tones" → "brown beige olive khaki")
4. Infer occasion from context (e.g. "date night" → "party evening")
5. Infer likely gender if contextual clues exist
6. Add relevant style descriptors and fabric hints
7. Include terms for BOTH upper body and lower body garments to ensure variety in results

Rules:
- Output ONLY a single expanded search string — no JSON, no explanation, no bullet points
- Keep it under 100 words
- Do NOT repeat the original query verbatim at the start
- Do NOT hallucinate attributes the user clearly did not intend
- The expanded query will be embedded using the same model as the products, so match the vocabulary style"""

QUERY_ENRICHMENT_USER_TEMPLATE = """Original user query: "{query}"

Expand this into a rich fashion search query."""


def enrich_query(
    model_name: str,
    query: str,
    *,
    system_prompt: str | None = None,
) -> str:
    """Enrich a user's raw fashion query into a semantically richer search string.

    Delegates the LLM call to the gateway (Vertex primary, OpenAI failover) to expand
    the query with inferred attributes, synonyms, and fashion vocabulary aligned with the
    embedding text format used at ingestion.

    system_prompt: optional override for the system prompt. Defaults to the
    module-level QUERY_ENRICHMENT_SYSTEM_PROMPT constant so existing callers
    are unaffected.
    """
    prompt = system_prompt if system_prompt is not None else QUERY_ENRICHMENT_SYSTEM_PROMPT
    user_message = QUERY_ENRICHMENT_USER_TEMPLATE.format(query=query)

    # Connectivity, retry/backoff and provider selection are owned by the gateway.
    # On failure it raises LLMGatewayError (a RuntimeError), which callers already handle.
    enriched = generate_text(
        task="query_enrichment",
        model=model_name,
        system_prompt=prompt,
        user_message=user_message,
    ).strip()
    logger.info(
        "Query enrichment succeeded: original='%s' enriched='%s'",
        query, enriched,
    )
    return enriched
