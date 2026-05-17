import logging
import time

from google import genai

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
BACKOFF_SECONDS = [1, 2, 4]

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
    api_key: str,
    model_name: str,
    query: str,
    *,
    system_prompt: str | None = None,
) -> str:
    """Enrich a user's raw fashion query into a semantically richer search string.

    Uses Gemini to expand the query with inferred attributes, synonyms, and
    fashion vocabulary aligned with the embedding text format used at ingestion.

    system_prompt: optional override for the system prompt. Defaults to the
    module-level QUERY_ENRICHMENT_SYSTEM_PROMPT constant so existing callers
    are unaffected.
    """
    prompt = system_prompt if system_prompt is not None else QUERY_ENRICHMENT_SYSTEM_PROMPT
    client = genai.Client(api_key=api_key)
    user_message = QUERY_ENRICHMENT_USER_TEMPLATE.format(query=query)

    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=[
                    prompt + "\n\n" + user_message,
                ],
            )
            enriched = response.text.strip()
            logger.info(
                "Query enrichment succeeded: original='%s' enriched='%s'",
                query, enriched,
            )
            return enriched

        except Exception as e:
            last_error = e
            logger.warning(
                "Attempt %d/%d: Query enrichment error: %s",
                attempt + 1, MAX_RETRIES, e,
            )
            if attempt < MAX_RETRIES - 1:
                time.sleep(BACKOFF_SECONDS[attempt])

    raise RuntimeError(
        f"Query enrichment failed after {MAX_RETRIES} attempts: {last_error}"
    )
