import base64
import json
import logging
import time
from pathlib import Path

from google import genai

from src.config import get_settings

logger = logging.getLogger(__name__)

VISION_PROMPT = """Analyze this garment image and return a JSON object with exactly these fields:
- category: one of [dress, saree, shirt, blazer, trousers, skirt, shoes, jacket, kurta, lehenga, gown, top, other]
- wear_type: one of [topwear, bottomwear, full_body, accessory] — classify as topwear (shirts, blazers, jackets, tops, kurtas), bottomwear (trousers, skirts), full_body (dresses, sarees, lehengas, gowns), or accessory (shoes, bags, other)
- colors: array of dominant colors from [red, blue, green, yellow, black, white, pink, purple, orange, gold, silver, beige, brown, maroon, navy, grey, multicolor]
- occasion: one of [wedding, party, casual, formal, festive, office, traditional]
- style_tags: array of 3-5 descriptive tags (e.g. embroidered, floral, silk, vintage, modern)
- caption: one-line description of the garment. Focus on the clothes, not the model wearing them.
- pattern: visual pattern if visible (e.g. solid, striped, checked, floral, printed) or null
- fabric_hint: visible fabric type if identifiable (e.g. cotton, denim, silk, wool, synthetic) or null

Return ONLY valid JSON, no other text."""

MAX_RETRIES = 3
BACKOFF_SECONDS = [1, 2, 4]


def _parse_vision_response(raw_text: str) -> dict:
    cleaned = raw_text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return json.loads(cleaned.strip())


def extract_metadata(
    image_path: Path,
    model_name: str,
) -> dict:
    """Call Gemini vision model via Vertex AI to extract raw visual metadata from an image."""
    _s = get_settings()
    client = genai.Client(vertexai=True, project=_s.google_cloud_project, location=_s.google_cloud_location)

    image_bytes = image_path.read_bytes()
    image_part = genai.types.Part.from_bytes(
        data=image_bytes,
        mime_type=f"image/{image_path.suffix.lstrip('.').replace('jpg', 'jpeg')}",
    )

    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=[image_part, VISION_PROMPT],
            )
            raw_text = response.text
            parsed = _parse_vision_response(raw_text)
            parsed["raw_vision_output"] = raw_text
            parsed["model_version"] = model_name

            logger.info(
                "Vision extraction succeeded for %s: category=%s colors=%s",
                image_path.name,
                parsed.get("category"),
                parsed.get("colors"),
            )
            return parsed

        except json.JSONDecodeError as e:
            last_error = e
            logger.warning(
                "Attempt %d/%d: Failed to parse vision response for %s: %s",
                attempt + 1, MAX_RETRIES, image_path.name, e,
            )
        except Exception as e:
            last_error = e
            logger.warning(
                "Attempt %d/%d: Vision API error for %s: %s",
                attempt + 1, MAX_RETRIES, image_path.name, e,
            )

        if attempt < MAX_RETRIES - 1:
            time.sleep(BACKOFF_SECONDS[attempt])

    raise RuntimeError(
        f"Vision extraction failed after {MAX_RETRIES} attempts for "
        f"{image_path.name}: {last_error}"
    )
