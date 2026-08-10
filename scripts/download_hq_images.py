"""One-time batch download of high-quality images from Kaggle to replace
the low-quality set currently served by the app.

Usage:
    venv/bin/python scripts/download_hq_images.py
"""
import logging
import os
import shutil
from pathlib import Path

import kagglehub

from src.config import get_settings
from src.ingestion import scan_image_folder

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATASET_HANDLE = "paramaggarwal/fashion-product-images-dataset"

# Candidate internal path templates, tried in order against the first file
# only. Whichever succeeds is reused for the rest of the run.
PATH_TEMPLATES = [
    "images/{filename}",
    "fashion-dataset/images/{filename}",
    "fashion-product-images/images/{filename}",
]


def _configure_kaggle_auth(kaggle_username: str, kaggle_key: str) -> None:
    if not kaggle_username or not kaggle_key:
        raise RuntimeError(
            "KAGGLE_USERNAME and KAGGLE_KEY must be set in .env before running this script. "
            "Get them from https://www.kaggle.com/settings -> API -> Create New Token."
        )
    os.environ["KAGGLE_USERNAME"] = kaggle_username
    os.environ["KAGGLE_KEY"] = kaggle_key


def _resolve_path_template(first_filename: str) -> str:
    for template in PATH_TEMPLATES:
        dataset_path = template.format(filename=first_filename)
        try:
            kagglehub.dataset_download(DATASET_HANDLE, path=dataset_path)
        except (ValueError, OSError) as e:
            logger.info("Template %r failed for %s: %s", template, first_filename, e)
            continue
        else:
            logger.info("Resolved dataset path template: %r", template)
            return template
    raise RuntimeError(
        f"Could not find {first_filename!r} in {DATASET_HANDLE} under any known path template "
        f"({PATH_TEMPLATES}). Check the dataset's file listing on Kaggle and add the correct "
        f"template to PATH_TEMPLATES."
    )


def _download_one(filename: str, path_template: str, dest_folder: Path) -> bool:
    dest_path = dest_folder / filename
    if dest_path.exists():
        logger.info("Skipping %s — already present in %s", filename, dest_folder)
        return True

    dataset_path = path_template.format(filename=filename)
    try:
        downloaded_path = kagglehub.dataset_download(DATASET_HANDLE, path=dataset_path)
    except (ValueError, OSError) as e:
        logger.error("Failed to download %s: %s", filename, e)
        return False

    shutil.copyfile(downloaded_path, dest_path)
    logger.info("Downloaded %s -> %s", filename, dest_path)
    return True


def main() -> None:
    settings = get_settings()
    _configure_kaggle_auth(settings.kaggle_username, settings.kaggle_key)

    if not settings.hq_image_folder_path:
        raise RuntimeError("HQ_IMAGE_FOLDER_PATH must be set in .env before running this script.")

    dest_folder = Path(settings.hq_image_folder_path)
    dest_folder.mkdir(parents=True, exist_ok=True)

    images = scan_image_folder(settings.image_folder_path)
    filenames = [p.name for p in images]
    if not filenames:
        logger.warning("No images found in %s — nothing to do.", settings.image_folder_path)
        return

    logger.info("Found %d images currently in the app. Resolving dataset path layout...", len(filenames))
    path_template = _resolve_path_template(filenames[0])

    downloaded, skipped, failed = 0, 0, []
    for filename in filenames:
        dest_path = dest_folder / filename
        already_present = dest_path.exists()
        ok = _download_one(filename, path_template, dest_folder)
        if not ok:
            failed.append(filename)
        elif already_present:
            skipped += 1
        else:
            downloaded += 1

    logger.info(
        "Done. downloaded=%d skipped=%d failed=%d total=%d",
        downloaded, skipped, len(failed), len(filenames),
    )
    if failed:
        logger.warning("Failed filenames (still served from the low-res folder): %s", failed)


if __name__ == "__main__":
    main()
