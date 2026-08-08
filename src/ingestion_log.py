import csv
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

LOG_COLUMNS = [
    "ingested_at",
    "product_id",
    "image_path",
    "category",
    "wear_type",
    "colors",
    "occasion",
    "style_tags",
    "caption",
    "pattern",
    "fabric_hint",
    "gender",
    "product_display_name",
    "season",
    "model_version",
    "file_hash",
]


def append_ingestion_log_row(csv_path: str, metadata: dict) -> None:
    path = Path(csv_path)
    file_exists = path.exists()

    row = {}
    for column in LOG_COLUMNS:
        value = metadata.get(column, "")
        if isinstance(value, list):
            value = ";".join(str(v) for v in value)
        row[column] = value

    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_COLUMNS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)
