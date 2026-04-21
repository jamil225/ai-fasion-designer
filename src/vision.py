import json
import logging
import time
from pathlib import Path

from google import genai

from src.taxonomy import normalize_vision_output

logger = logging.getLogger(__name__)

VISION_PROMPT = """Analyze this garment image and return a JSON object with:
- category: one of [dress, saree, shirt, blazer, trousers, skirt, shoes, jacket, kurta, lehenga, gown, top, other]
- colors: array of dominant colors from [red, blue, green, yellow, black, white, pink, purple, orange, gold, silver, beige, brown, maroon, navy, grey, multicolor]
- occasion: one of [wedding, party, casual, formal, festive, office, traditional]
- style_tags: array of 3-5 descriptive tags (e.g. embroidered, floral, silk, vintage, modern)
- caption: one-line description of the garment Focus on the clothes not on the model wearing it details.

Return ONLY valid JSON, no other text."""

MAX_RETRIES = 3
BACKOFF_SECONDS = [1, 2, 4]


def _analyze_image(client: genai.Client, image_path: Path) -> str:
    uploaded_file = client.files.upload(file=image_path)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[VISION_PROMPT, uploaded_file],
    )
    return response.text


def _parse_vision_response(raw_text: str) -> dict:
    cleaned = raw_text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return json.loads(cleaned.strip())


def extract_metadata(api_key: str, image_path: Path) -> dict:
    client = genai.Client(api_key=api_key)

    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            raw_text = _analyze_image(client, image_path)
            parsed = _parse_vision_response(raw_text)
            normalized = normalize_vision_output(parsed)
            normalized["raw_vision_output"] = raw_text
            normalized["model_version"] = "gemini-2.5-flash"

            logger.info(
                "Vision extraction succeeded for %s: category=%s colors=%s",
                image_path.name,
                normalized["category"],
                normalized["colors"],
            )
            return normalized

        except json.JSONDecodeError as e:
            last_error = e
            logger.warning(
                "Attempt %d/%d: Failed to parse Gemini response for %s: %s",
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
