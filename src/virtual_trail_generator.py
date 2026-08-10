"""
4-Angle Image Generation Service using Nano Banana (Gemini 2.5 Flash Image).

Takes a sari product image + a default model reference image and generates
4 angle variants: front, right side, back, left profile.
"""

import os
import time
import traceback
from io import BytesIO
from PIL import Image
from google import genai
from google.genai import types

import config

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Delay between API calls to avoid rate limits (seconds)
API_CALL_DELAY = 25

# Output image size: "1K", "2K", or "4K" (use "1K" during development to save tokens)
OUTPUT_IMAGE_SIZE = "1K"

# ---------------------------------------------------------------------------
# Angle prompt definitions
# Each prompt explicitly labels the two input images so the model knows:
#   - Image 1 = face/body reference (use ONLY her face and body shape)
#   - Image 2 = the sari product (dress her in THIS exact sari)
# ---------------------------------------------------------------------------

ANGLE_PROMPTS = {
    "front": (
        "I am providing two images:\n"
        "- IMAGE 1 (first image): A reference photo of a female model. Use ONLY her face, "
        "hairstyle, skin tone, and body proportions from this image. IGNORE her clothing entirely.\n"
        "- IMAGE 2 (second image): A sari product photo. This is the EXACT sari that the model "
        "must be wearing in the generated image. Preserve every detail of this sari — its exact "
        "colors, patterns, embroidery, border designs, fabric texture, and sheen.\n\n"
        "TASK: Generate a photorealistic, full-body photograph of the woman from Image 1, "
        "now wearing the sari from Image 2. She is facing directly toward the camera in a "
        "natural, confident standing pose with hands relaxed at her sides. The sari is draped "
        "in traditional Nivi style with neat pleats tucked at the waist and the pallu draped "
        "over the left shoulder.\n\n"
        "SETTING: Professional fashion photography studio with a smooth, solid warm beige/cream "
        "backdrop and soft diffused lighting. Full body visible head to toe. "
        "This should look like a premium Amazon e-commerce product listing photo."
    ),
    "right_side": (
        "I am providing two images:\n"
        "- IMAGE 1 (first image): A reference photo of a female model. Use ONLY her face, "
        "hairstyle, skin tone, and body proportions from this image. IGNORE her clothing entirely.\n"
        "- IMAGE 2 (second image): A sari product photo. This is the EXACT sari that the model "
        "must be wearing in the generated image. Preserve every detail of this sari — its exact "
        "colors, patterns, embroidery, border designs, fabric texture, and sheen.\n\n"
        "TASK: Generate a photorealistic, full-body photograph of the woman from Image 1, "
        "now wearing the sari from Image 2. She is turned approximately 45 degrees to her right, "
        "showing a right profile view. Her face is slightly turned toward the camera with a soft "
        "expression. The sari drape, pallu fall, and fabric details must be clearly visible from "
        "this side angle.\n\n"
        "SETTING: Professional fashion photography studio with a smooth, solid warm beige/cream "
        "backdrop and soft diffused lighting. Full body visible head to toe."
    ),
    "back": (
        "I am providing two images:\n"
        "- IMAGE 1 (first image): A reference photo of a female model. Use ONLY her face, "
        "hairstyle, skin tone, and body proportions from this image. IGNORE her clothing entirely.\n"
        "- IMAGE 2 (second image): A sari product photo. This is the EXACT sari that the model "
        "must be wearing in the generated image. Preserve every detail of this sari — its exact "
        "colors, patterns, embroidery, border designs, fabric texture, and sheen.\n\n"
        "TASK: Generate a photorealistic, full-body photograph of the woman from Image 1, "
        "now wearing the sari from Image 2, with her back fully facing the camera. Show the "
        "blouse back design, the pallu falling over the shoulder and down the back, and the "
        "overall drape from behind. Her head is slightly turned to show a partial profile. "
        "The sari fabric, colors, patterns, and embroidery must be accurately preserved "
        "from this rear angle.\n\n"
        "SETTING: Professional fashion photography studio with a smooth, solid warm beige/cream "
        "backdrop and soft diffused lighting. Full body visible head to toe."
    ),
    "left_profile": (
        "I am providing two images:\n"
        "- IMAGE 1 (first image): A reference photo of a female model. Use ONLY her face, "
        "hairstyle, skin tone, and body proportions from this image. IGNORE her clothing entirely.\n"
        "- IMAGE 2 (second image): A sari product photo. This is the EXACT sari that the model "
        "must be wearing in the generated image. Preserve every detail of this sari — its exact "
        "colors, patterns, embroidery, border designs, fabric texture, and sheen.\n\n"
        "TASK: Generate a photorealistic, full-body photograph of the woman from Image 1, "
        "now wearing the sari from Image 2. She is turned approximately 45 degrees to her left, "
        "showing a left profile view. Her face is slightly turned toward the camera with a "
        "composed expression. The sari pleats, fabric texture, and all design details must be "
        "clearly visible from this angle.\n\n"
        "SETTING: Professional fashion photography studio with a smooth, solid warm beige/cream "
        "backdrop and soft diffused lighting. Full body visible head to toe."
    ),
}

ANGLE_ORDER = ["front", "right_side", "back", "left_profile"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_image_as_part(path: str) -> types.Part:
    """Load an image file at full quality and return as a genai Part."""
    img = Image.open(path)
    img.load()

    # Convert to RGB if necessary
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    buf = BytesIO()
    img.save(buf, format="PNG")
    return types.Part.from_bytes(data=buf.getvalue(), mime_type="image/png")


# ---------------------------------------------------------------------------
# Core generation
# ---------------------------------------------------------------------------

def generate_angles(
    sari_image_path: str,
    output_dir: str,
    product_name: str,
    model_image_path: str | None = None,
) -> dict:
    """
    Generate four full-body sari images from front, right-side, back, and left-profile angles.
    
    Args:
        sari_image_path: Path to the sari product image.
        output_dir: Directory where generated images are saved.
        product_name: Name used to construct output filenames.
        model_image_path: Optional path to the model reference image. Uses the configured
            default image when omitted.
    
    Returns:
        A mapping of angle names to saved image paths or error details.
    
    Raises:
        FileNotFoundError: If the sari image or model reference image does not exist.
    """
    if model_image_path is None:
        model_image_path = config.DEFAULT_MODEL_IMAGE

    # Validate inputs
    if not os.path.exists(sari_image_path):
        raise FileNotFoundError(f"Sari image not found: {sari_image_path}")
    if not os.path.exists(model_image_path):
        raise FileNotFoundError(
            f"Default model image not found: {model_image_path}. "
            "Please place your model reference image at models/default_model.png"
        )

    os.makedirs(output_dir, exist_ok=True)

    # Load reference images at full quality
    model_ref_part = _load_image_as_part(model_image_path)
    sari_ref_part = _load_image_as_part(sari_image_path)

    # Init Vertex AI client (uses Application Default Credentials)
    client = genai.Client(vertexai=True, project=config.GOOGLE_CLOUD_PROJECT, location=config.GOOGLE_CLOUD_LOCATION)

    results = {}

    for idx, angle_key in enumerate(ANGLE_ORDER):
        prompt = ANGLE_PROMPTS[angle_key]
        out_filename = f"{product_name}_{angle_key}.png"
        out_path = os.path.join(output_dir, out_filename)

        # Rate-limit delay between calls (skip before first)
        if idx > 0:
            print(f"  ⏳ Waiting {API_CALL_DELAY}s before next call (rate limit)...")
            time.sleep(API_CALL_DELAY)

        try:
            print(f"  → Generating {angle_key} angle for '{product_name}'...")

            response = client.models.generate_content(
                model=config.IMAGE_MODEL,
                contents=[
                    "IMAGE 1 (model reference — use her face and body ONLY, ignore her clothes):",
                    model_ref_part,
                    "IMAGE 2 (sari product — dress the model in THIS exact sari):",
                    sari_ref_part,
                    prompt,
                ],
                config=types.GenerateContentConfig(
                    response_modalities=["TEXT", "IMAGE"],
                ),
            )

            # Extract generated image from response
            saved = False
            if response.candidates:
                for part in response.candidates[0].content.parts:
                    if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                        image_data = part.inline_data.data
                        img = Image.open(BytesIO(image_data))
                        img.save(out_path, "PNG")
                        results[angle_key] = out_path
                        saved = True
                        print(f"  ✓ Saved {angle_key} → {out_path}")
                        break

            if not saved:
                text_parts = []
                if response.candidates:
                    for part in response.candidates[0].content.parts:
                        if part.text:
                            text_parts.append(part.text)
                error_msg = " | ".join(text_parts) if text_parts else "No image in response"
                results[angle_key] = {"error": error_msg}
                print(f"  ✗ {angle_key} failed: {error_msg}")

        except Exception as e:
            traceback.print_exc()
            results[angle_key] = {"error": str(e)}
            print(f"  ✗ {angle_key} exception: {e}")

    return results


def generate_for_batch(
    sari_image_paths: list[str],
    base_output_dir: str,
    product_names: list[str],
    model_image_path: str | None = None,
) -> dict:
    """
    Generate 4-angle images for a batch of sari products.

    Returns:
        dict mapping product_name → angle results dict
    """
    all_results = {}
    total = len(sari_image_paths)

    for i, (sari_path, name) in enumerate(zip(sari_image_paths, product_names), 1):
        print(f"\n[{i}/{total}] Processing product: {name}")
        product_output_dir = os.path.join(base_output_dir, name)
        result = generate_angles(
            sari_image_path=sari_path,
            output_dir=product_output_dir,
            product_name=name,
            model_image_path=model_image_path,
        )
        all_results[name] = result

    return all_results


