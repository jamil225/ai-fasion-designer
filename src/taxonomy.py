import logging

logger = logging.getLogger(__name__)

CATEGORIES = {
    "dress", "saree", "shirt", "blazer", "trousers", "skirt", "shoes",
    "jacket", "kurta", "lehenga", "gown", "top", "other",
}

OCCASIONS = {
    "wedding", "party", "casual", "formal", "festive", "office", "traditional",
}

COLORS = {
    "red", "blue", "green", "yellow", "black", "white", "pink", "purple",
    "orange", "gold", "silver", "beige", "brown", "maroon", "navy", "grey",
    "multicolor",
}

# Synonyms mapped to canonical color values
COLOR_SYNONYMS: dict[str, str] = {
    "crimson": "red",
    "scarlet": "red",
    "ruby": "red",
    "burgundy": "maroon",
    "wine": "maroon",
    "ivory": "white",
    "cream": "beige",
    "off-white": "beige",
    "tan": "beige",
    "khaki": "beige",
    "charcoal": "grey",
    "gray": "grey",
    "slate": "grey",
    "ash": "grey",
    "midnight": "navy",
    "indigo": "navy",
    "cobalt": "blue",
    "teal": "blue",
    "turquoise": "blue",
    "aqua": "blue",
    "cyan": "blue",
    "sky blue": "blue",
    "royal blue": "blue",
    "baby blue": "blue",
    "magenta": "pink",
    "rose": "pink",
    "blush": "pink",
    "fuchsia": "pink",
    "coral": "orange",
    "peach": "orange",
    "rust": "orange",
    "amber": "orange",
    "lime": "green",
    "olive": "green",
    "emerald": "green",
    "mint": "green",
    "sage": "green",
    "forest green": "green",
    "lavender": "purple",
    "violet": "purple",
    "plum": "purple",
    "lilac": "purple",
    "mauve": "purple",
    "lemon": "yellow",
    "mustard": "yellow",
    "champagne": "gold",
    "bronze": "gold",
    "copper": "brown",
    "chocolate": "brown",
    "caramel": "brown",
    "espresso": "brown",
    "coffee": "brown",
    "multi": "multicolor",
    "multi-colored": "multicolor",
    "multicolored": "multicolor",
    "multi-colour": "multicolor",
}

CATEGORY_SYNONYMS: dict[str, str] = {
    "sari": "saree",
    "t-shirt": "shirt",
    "tshirt": "shirt",
    "t shirt": "shirt",
    "blouse": "top",
    "crop top": "top",
    "tank top": "top",
    "camisole": "top",
    "pants": "trousers",
    "jeans": "trousers",
    "chinos": "trousers",
    "coat": "jacket",
    "overcoat": "jacket",
    "suit jacket": "blazer",
    "sport coat": "blazer",
    "lehnga": "lehenga",
    "lengha": "lehenga",
    "evening gown": "gown",
    "maxi dress": "dress",
    "mini dress": "dress",
    "midi dress": "dress",
    "frock": "dress",
    "sandals": "shoes",
    "heels": "shoes",
    "boots": "shoes",
    "sneakers": "shoes",
    "loafers": "shoes",
}

OCCASION_SYNONYMS: dict[str, str] = {
    "bridal": "wedding",
    "reception": "wedding",
    "engagement": "wedding",
    "cocktail": "party",
    "clubbing": "party",
    "night out": "party",
    "evening": "party",
    "work": "office",
    "business": "formal",
    "professional": "formal",
    "everyday": "casual",
    "daily": "casual",
    "weekend": "casual",
    "streetwear": "casual",
    "celebration": "festive",
    "holiday": "festive",
    "festival": "festive",
    "ethnic": "traditional",
    "cultural": "traditional",
    "religious": "traditional",
    "ceremonial": "traditional",
    "puja": "traditional",
}


def normalize_color(raw: str) -> str:
    lowered = raw.strip().lower()
    if lowered in COLORS:
        return lowered
    if lowered in COLOR_SYNONYMS:
        return COLOR_SYNONYMS[lowered]
    logger.warning("Unrecognized color '%s', keeping as-is", raw)
    return lowered


def normalize_colors(raw_colors: list[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for c in raw_colors:
        norm = normalize_color(c)
        if norm not in seen:
            seen.add(norm)
            normalized.append(norm)
    return normalized


def normalize_category(raw: str) -> str:
    lowered = raw.strip().lower()
    if lowered in CATEGORIES:
        return lowered
    if lowered in CATEGORY_SYNONYMS:
        return CATEGORY_SYNONYMS[lowered]
    logger.warning("Unrecognized category '%s', mapping to 'other'", raw)
    return "other"


def normalize_occasion(raw: str) -> str:
    lowered = raw.strip().lower()
    if lowered in OCCASIONS:
        return lowered
    if lowered in OCCASION_SYNONYMS:
        return OCCASION_SYNONYMS[lowered]
    logger.warning("Unrecognized occasion '%s', mapping to 'casual'", raw)
    return "casual"


def normalize_vision_output(raw: dict) -> dict:
    return {
        "category": normalize_category(raw.get("category", "other")),
        "colors": normalize_colors(raw.get("colors", [])),
        "occasion": normalize_occasion(raw.get("occasion", "casual")),
        "style_tags": [tag.strip().lower() for tag in raw.get("style_tags", [])],
        "caption": raw.get("caption", "").strip(),
    }
