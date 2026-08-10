# HQ Image Batch Download Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One-time script that downloads the high-quality counterpart of every image currently in `IMAGE_FOLDER_PATH` from the `paramaggarwal/fashion-product-images-dataset` Kaggle dataset into a new local folder, so the app can be pointed at higher-quality images without touching ingestion or Pinecone.

**Architecture:** A single new script (`scripts/download_hq_images.py`) reuses the existing `scan_image_folder()` helper to get the exact filename list already known to the app, then downloads each matching file via `kagglehub.dataset_download(handle, path=..., output_dir=...)` into a new configured folder. No runtime/request-path code changes.

**Tech Stack:** Python 3.11+, `kagglehub` (new dependency), existing `pydantic-settings` config pattern.

## Global Constraints

- Type hints on all function signatures (CLAUDE.md §8).
- Catch specific exceptions, never bare `except` (CLAUDE.md §8).
- All secrets/paths via `.env` + `pydantic-settings` — no hardcoded keys/paths (CLAUDE.md §8).
- Do NOT write automated unit/integration tests — manual verification only (CLAUDE.md §9).
- Do NOT create `utils/`, `helpers/`, `common/` directories — keep flat (CLAUDE.md §9).
- No wrapper/shim/adapter classes around SDK behavior (CLAUDE.md §9, DEC-023).
- One task → one commit, referencing this plan (CLAUDE.md §7).
- Never `git push` without explicit per-push approval (CLAUDE.md §9).

---

## Task 1: Config and dependency for the HQ download

**Files:**
- Modify: `requirements.txt`
- Modify: `src/config.py` (Settings class, in the "Application Settings" block around line 104-106)
- Modify: `.env.example` (Application Settings section, after `IMAGE_FOLDER_PATH`)

**Interfaces:**
- Produces: `Settings.hq_image_folder_path: str`, `Settings.kaggle_username: str`, `Settings.kaggle_key: str`, all readable via `get_settings()` — Task 2 consumes these.

- [ ] **Step 1: Add `kagglehub` to `requirements.txt`**

Add a new line (keep alphabetical grouping consistent with the rest of the file — append near the bottom, after `litellm`):

```
kagglehub
```

- [ ] **Step 2: Install it into the project venv**

Run: `venv/bin/pip install kagglehub`
Expected: installs successfully, no errors.

- [ ] **Step 3: Add the three new settings fields**

In `src/config.py`, inside the `Settings` class, in the "Application Settings" block (currently `app_api_key`, `image_folder_path`, `csv_file_path`, `default_top_k`, `best_match_score_threshold`), add:

```python
    hq_image_folder_path: str = ""
    kaggle_username: str = ""
    kaggle_key: str = ""
```

- [ ] **Step 4: Add matching entries to `.env.example`**

In `.env.example`, right after the `IMAGE_FOLDER_PATH=/path/to/images` line, add:

```
HQ_IMAGE_FOLDER_PATH=/path/to/hq_images
KAGGLE_USERNAME=your-kaggle-username
KAGGLE_KEY=your-kaggle-api-key
```

- [ ] **Step 5: Manually verify settings load correctly**

Run:
```bash
venv/bin/python -c "
from src.config import get_settings
s = get_settings()
print('hq_image_folder_path:', repr(s.hq_image_folder_path))
print('kaggle_username:', repr(s.kaggle_username))
print('kaggle_key set:', bool(s.kaggle_key))
"
```
Expected: prints three lines with no traceback. Values will be empty strings unless you've already added them to your local `.env` — that's fine, this step only confirms the fields exist and load without error.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt src/config.py .env.example
git commit -m "$(cat <<'EOF'
feat(hq-images): add kagglehub dependency and HQ image config

Adds hq_image_folder_path, kaggle_username, kaggle_key settings for
the one-time high-quality image download script (Task 1 of
docs/superpowers/plans/2026-08-08-hq-image-batch-download.md).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: `scripts/download_hq_images.py`

**Files:**
- Create: `scripts/download_hq_images.py`

**Interfaces:**
- Consumes: `scan_image_folder(folder_path: str) -> list[Path]` from `src/ingestion.py` (existing, unmodified); `get_settings() -> Settings` from `src/config.py`, including `hq_image_folder_path`, `kaggle_username`, `kaggle_key`, `image_folder_path` (Task 1).
- Produces: a runnable script with a `main() -> None` entry point. No other code depends on this script's internals — it's a standalone CLI tool.

### Design notes for the implementer

The Kaggle dataset's exact internal folder layout for image files is not confirmed ahead of time (see the spec's "Open items to verify"). The script handles this by trying a short ordered list of path templates against the *first* file only, keeping whichever one succeeds, and reusing that same template for every subsequent file (the dataset has one consistent internal layout, so this only needs to be resolved once per run).

- [ ] **Step 1: Create `scripts/` directory and the script file with imports, constants, and the path-template resolver**

```python
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
```

- [ ] **Step 2: Add the per-file download + batch loop + summary**

Append to the same file:

```python
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
```

- [ ] **Step 3: Manually verify the script's config/auth guard rails without real credentials**

Run (with `.env` still missing `KAGGLE_USERNAME`/`KAGGLE_KEY`, or with them temporarily blanked):
```bash
venv/bin/python scripts/download_hq_images.py
```
Expected: fails fast with `RuntimeError: KAGGLE_USERNAME and KAGGLE_KEY must be set in .env...` — confirms the auth guard runs before any network call.

- [ ] **Step 4: Get real Kaggle credentials and run the script end-to-end**

This step needs your action, since it requires your personal Kaggle account:
1. Go to https://www.kaggle.com/settings → API → "Create New Token" (downloads `kaggle.json` with `username` and `key`).
2. Add `KAGGLE_USERNAME=<username>` and `KAGGLE_KEY=<key>` to your local `.env`.
3. Add `HQ_IMAGE_FOLDER_PATH=<some new local path, e.g. /Users/dev/ai-fasion-designer/hq_images>` to `.env` if not already set.
4. Run: `venv/bin/python scripts/download_hq_images.py`
5. Confirm the log ends with `Done. downloaded=N skipped=0 failed=M total=N+M` where `N+M` matches the number of files in your current `IMAGE_FOLDER_PATH`.
6. If `failed` is non-zero, check the logged filenames — those images have no high-quality match in the dataset and will keep serving the low-res version until resolved (this is expected per the spec's non-goals).
7. Re-run the script once more — expected: `downloaded=0 skipped=N` (idempotency check).

- [ ] **Step 5: Spot-check quality improvement**

Pick one filename that downloaded successfully and compare file sizes:
```bash
ls -la "$IMAGE_FOLDER_PATH/<filename>" "$HQ_IMAGE_FOLDER_PATH/<filename>"
```
Expected: the HQ file is noticeably larger in bytes (and, if you open both, visibly higher resolution).

- [ ] **Step 6: Switch the app to serve the HQ folder**

Edit `.env`: change `IMAGE_FOLDER_PATH` to the same value as `HQ_IMAGE_FOLDER_PATH`. Restart the backend server (`PORT=8083 venv/bin/uvicorn src.main:app --port 8083 --reload` per CLAUDE.md §1.2). Open Swagger UI (`/docs`) and call `GET /v1/images/{filename}` for a known filename — confirm it returns the high-quality file. Load the frontend and confirm a search still returns results with higher-quality images rendered (proving Pinecone/ingestion was unaffected).

- [ ] **Step 7: Commit**

```bash
git add scripts/download_hq_images.py
git commit -m "$(cat <<'EOF'
feat(hq-images): add one-time HQ image batch download script

Downloads the high-quality counterpart of every image currently in
IMAGE_FOLDER_PATH from paramaggarwal/fashion-product-images-dataset
via kagglehub, into a new configurable folder. Switching
IMAGE_FOLDER_PATH to that folder in .env is what actually changes
what the app serves — ingestion/Pinecone are untouched
(Task 2 of docs/superpowers/plans/2026-08-08-hq-image-batch-download.md).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

Note: do not commit `.env` itself (already gitignored) — only the script and the Task 1 changes.
