import csv
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

CSV_COLUMNS = [
    "image_id", "gender", "masterCategory", "subCategory",
    "articleType", "baseColour", "season", "year", "usage", "productDisplayName",
]


def load_csv_lookup(csv_path: str) -> dict[str, dict]:
    """Load vendor CSV into a dict keyed by image_id (filename stem).

    Returns an empty dict if csv_path is not set or the file does not exist.
    Should be called once before the ingestion loop.
    """
    if not csv_path:
        logger.warning("CSV_FILE_PATH not configured — CSV enrichment disabled")
        return {}

    path = Path(csv_path)
    if not path.exists():
        logger.warning("CSV file not found: %s — CSV enrichment disabled", csv_path)
        return {}

    lookup: dict[str, dict] = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            image_id = row.get("image_id", "").strip()
            if not image_id:
                continue
            lookup[image_id] = {
                col: row.get(col, "").strip()
                for col in CSV_COLUMNS
                if col in row
            }

    logger.info("Loaded %d CSV rows from %s", len(lookup), csv_path)
    return lookup


def get_csv_row(lookup: dict[str, dict], image_path: Path) -> dict | None:
    """Return the CSV row for this image matched by filename stem, or None.

    Example: image_path "15970.jpg" looks up key "15970".
    """
    row = lookup.get(image_path.stem)
    if row is None:
        logger.warning(
            "No CSV row for image_id=%s — vision-only path will be used",
            image_path.stem,
        )
    return row
