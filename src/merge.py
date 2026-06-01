import json
import logging
import time

from google import genai

from src.config import get_settings

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
BACKOFF_SECONDS = [1, 2, 4]

MERGE_SYSTEM_PROMPT = """You are a fashion product data enrichment assistant.
You will receive two inputs:
1. VISION_ANALYSIS: raw visual analysis from a vision model — use this as your starting point for descriptive fields.
2. VENDOR_DATA: structured vendor CSV data — use this to correct factual fields where vision may be inaccurate.

Rules:
- VISION_ANALYSIS is the base for descriptive fields: style_tags, caption, pattern, fabric_hint.
- VENDOR_DATA corrects factual fields when present: colors (from baseColour), category (from articleType), occasion (from usage).
- If a factual field exists in VENDOR_DATA, it takes priority over the vision model's output.
- If VENDOR_DATA is empty or missing a field, fall back to VISION_ANALYSIS for that field.
- Return ONLY valid JSON with no markdown, no explanation, no extra text."""

MERGE_USER_TEMPLATE = """VISION_ANALYSIS:
{vision_json}

VENDOR_DATA:
{vendor_json}

Produce a single enriched JSON with exactly these fields:
- category: normalize articleType from VENDOR_DATA to one of [dress, saree, shirt, blazer, trousers, skirt, shoes, jacket, kurta, lehenga, gown, top, other]. Use vision category if VENDOR_DATA has no articleType.
- colors: array of canonical colors — use VENDOR_DATA.baseColour as the primary color, supplement with additional colors from VISION_ANALYSIS if relevant.
- occasion: normalize VENDOR_DATA.usage to one of [wedding, party, casual, formal, festive, office, traditional]. Use vision occasion if VENDOR_DATA has no usage.
- style_tags: array of 3-5 descriptive strings from VISION_ANALYSIS.
- caption: one-line description from VISION_ANALYSIS that incorporates any relevant product context.
- pattern: string or null from VISION_ANALYSIS (e.g. solid, striped, checked, floral, printed).
- fabric_hint: string or null from VISION_ANALYSIS (e.g. cotton, denim, silk, wool, synthetic).

Return ONLY valid JSON."""


def merge_product_data(
    model_name: str,
    vision_output: dict,
    csv_row: dict | None,
) -> dict:
    """Merge vision output with vendor CSV data using Gemini via Vertex AI.

    CSV corrects factual fields (colors, category, occasion).
    Vision provides descriptive fields (style_tags, caption, pattern, fabric_hint).
    If no CSV row, returns vision-only fallback without calling the LLM.
    """
    if csv_row is None:
        return _vision_only_fallback(vision_output)

    _s = get_settings()
    client = genai.Client(vertexai=True, project=_s.google_cloud_project, location=_s.google_cloud_location)

    # Exclude pipeline fields from what we send to the LLM
    vision_for_merge = {
        k: v for k, v in vision_output.items()
        if k not in ("raw_vision_output", "model_version")
    }
    vendor_json = json.dumps(csv_row, ensure_ascii=False)
    vision_json = json.dumps(vision_for_merge, ensure_ascii=False)
    user_message = MERGE_USER_TEMPLATE.format(
        vendor_json=vendor_json,
        vision_json=vision_json,
    )

    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=[
                    MERGE_SYSTEM_PROMPT + "\n\n" + user_message,
                ],
            )
            raw_text = response.text
            merged = _parse_merge_response(raw_text)
            # Pass through vision wear_type for three-tier resolution in ingestion
            merged["vision_wear_type"] = vision_output.get("wear_type")
            logger.info(
                "Merge succeeded: product=%s category=%s colors=%s",
                csv_row.get("productDisplayName", "unknown"),
                merged.get("category"),
                merged.get("colors"),
            )
            return merged

        except json.JSONDecodeError as e:
            last_error = e
            logger.warning(
                "Attempt %d/%d: Failed to parse merge response: %s",
                attempt + 1, MAX_RETRIES, e,
            )
        except Exception as e:
            last_error = e
            logger.warning(
                "Attempt %d/%d: Merge API error: %s",
                attempt + 1, MAX_RETRIES, e,
            )

        if attempt < MAX_RETRIES - 1:
            time.sleep(BACKOFF_SECONDS[attempt])

    raise RuntimeError(
        f"Merge failed after {MAX_RETRIES} attempts: {last_error}"
    )


def _parse_merge_response(raw_text: str) -> dict:
    cleaned = raw_text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return json.loads(cleaned.strip())


def _vision_only_fallback(vision_output: dict) -> dict:
    """No CSV row available — map vision fields directly to the merged schema.

    gender, product_display_name, season will be set to '' by ingestion.py.
    """
    logger.warning("No CSV row — using vision-only fallback for this image")
    return {
        "category": vision_output.get("category", "other"),
        "colors": vision_output.get("colors", []),
        "occasion": vision_output.get("occasion", "casual"),
        "style_tags": vision_output.get("style_tags", []),
        "caption": vision_output.get("caption", ""),
        "pattern": vision_output.get("pattern") or "",
        "fabric_hint": vision_output.get("fabric_hint") or "",
        "vision_wear_type": vision_output.get("wear_type"),
    }
