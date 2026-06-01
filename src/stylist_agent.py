import json
import logging
import time

from google import genai

from src.config import get_settings

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
BACKOFF_SECONDS = [1, 2, 4]

STYLIST_SYSTEM_PROMPT = """You are an expert fashion stylist AI. You receive a set of fashion products retrieved from a vector search and must create cohesive outfit combinations.

## Your Task
Create outfit combos by pairing topwear items with bottomwear items. Full-body items (dresses, sarees, lehengas, gowns) are standalone outfits — never pair them with other garments.

## Pairing Rules (STRICT)
1. **Gender consistency**: Never pair a men's top with a women's bottom or vice versa. Items with empty gender can pair with either.
2. **Color harmony**: Prefer complementary contrasts (navy+cream, black+gold), analogous combinations (blue+teal), or intentional monochrome. Avoid clashing combinations (red+orange, pink+red) unless the user explicitly asked for bold/clashing styles.
3. **Occasion coherence**: A formal blazer should not pair with casual denim. Match occasion tags between top and bottom.
4. **Season alignment**: Do not pair heavy winter jackets with light summer skirts.
5. **Style coherence**: Traditional kurtas pair with traditional bottomwear. Western tops pair with western bottoms. Do not cross cultural style lines unless fusion is explicitly requested.

## Output Format
Return ONLY valid JSON with this exact structure:
{
  "combos": [
    {
      "combo_rank": 1,
      "top_product_id": "the product_id of the topwear item",
      "bottom_product_id": "the product_id of the bottomwear item",
      "styling_rationale": "2-3 sentences explaining WHY these items pair well. Reference specific colors, occasion fit, and style principles."
    }
  ],
  "standalone_outfits": [
    {
      "product_id": "the product_id of the full_body item",
      "rationale": "1-2 sentences explaining why this full-body item works for the query."
    }
  ]
}

## Quality Standards
- Rank combos by overall styling quality (best first)
- Each rationale MUST reference specific attributes: mention actual colors, occasion, style tags
- If insufficient items exist to make good pairs, return fewer combos rather than forcing bad ones
- Never use the same item in multiple combos
- If ALL results are the same wear_type (e.g. all topwear, no bottomwear), return an empty combos array
- Items with wear_type "accessory" or "unknown" should not be used in combos

Return ONLY valid JSON, no markdown fences, no explanation outside the JSON."""

STYLIST_USER_TEMPLATE = """## User's Original Query
"{original_query}"

## Available Products from Vector Search
{products_json}

## Instructions
Create up to {combo_count} outfit combinations from these products. Each product has: product_id, image_path, category, colors, occasion, style_tags, caption, gender, wear_type, season, product_display_name, score.

Prioritize products with higher relevance scores when quality is otherwise equal."""


def _parse_stylist_response(raw_text: str) -> dict:
    cleaned = raw_text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return json.loads(cleaned.strip())


def _prepare_products_for_prompt(products: list[dict]) -> str:
    """Select only the fields the Stylist Agent needs to keep the prompt focused."""
    slim = []
    for p in products:
        slim.append({
            "product_id": p["product_id"],
            "image_path": p["image_path"],
            "category": p["category"],
            "colors": p["colors"],
            "occasion": p["occasion"],
            "style_tags": p["style_tags"],
            "caption": p["caption"],
            "gender": p["gender"],
            "wear_type": p["wear_type"],
            "season": p["season"],
            "product_display_name": p["product_display_name"],
            "score": round(p["score"], 4),
        })
    return json.dumps(slim, ensure_ascii=False, indent=2)


def curate_outfits(
    model_name: str,
    original_query: str,
    products: list[dict],
    combo_count: int,
    system_prompt: str | None = None,
) -> dict:
    """Use Gemini Pro via Vertex AI to curate outfit combinations from vector search results.

    Returns a dict with 'combos' and 'standalone_outfits' arrays.
    Each combo references products by product_id only — the caller resolves
    these back to full product metadata.
    """
    _s = get_settings()
    client = genai.Client(vertexai=True, project=_s.google_cloud_project, location=_s.google_cloud_location)

    effective_system_prompt = system_prompt if system_prompt is not None else STYLIST_SYSTEM_PROMPT
    products_json = _prepare_products_for_prompt(products)
    user_message = STYLIST_USER_TEMPLATE.format(
        original_query=original_query,
        products_json=products_json,
        combo_count=combo_count,
    )

    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=[
                    effective_system_prompt + "\n\n" + user_message,
                ],
            )
            raw_text = response.text
            parsed = _parse_stylist_response(raw_text)

            combos = parsed.get("combos", [])
            standalone = parsed.get("standalone_outfits", [])
            logger.info(
                "Stylist curation succeeded: %d combos, %d standalone outfits",
                len(combos), len(standalone),
            )
            return parsed

        except json.JSONDecodeError as e:
            last_error = e
            logger.warning(
                "Attempt %d/%d: Failed to parse stylist response: %s",
                attempt + 1, MAX_RETRIES, e,
            )
        except Exception as e:
            last_error = e
            logger.warning(
                "Attempt %d/%d: Stylist API error: %s",
                attempt + 1, MAX_RETRIES, e,
            )

        if attempt < MAX_RETRIES - 1:
            time.sleep(BACKOFF_SECONDS[attempt])

    raise RuntimeError(
        f"Stylist curation failed after {MAX_RETRIES} attempts: {last_error}"
    )
