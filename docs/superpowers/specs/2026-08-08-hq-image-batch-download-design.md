# Design: High-Quality Image Batch Download

**Date:** 2026-08-08
**Status:** Approved, ready for implementation plan

## Problem

The images currently served by the app (from `IMAGE_FOLDER_PATH`, ~35 files matching `Sheet-small.csv`) are low quality. The full-resolution counterpart of the same dataset — `paramaggarwal/fashion-product-images-dataset` on Kaggle — contains the same images (matched by filename/`image_id`) at higher quality. The goal is to fetch only the higher-quality images that correspond to what's already in the app, and serve those instead — with no change to ingestion, embeddings, or Pinecone data.

## Non-goals

- No re-ingestion. Pinecone metadata stores only the bare filename (`image_path`), so switching the served folder doesn't require touching vectors or metadata.
- No lazy/on-demand per-request download. This is a one-time (occasionally re-run) batch job, not a runtime code path.
- No new API endpoint, no changes to `src/main.py` routes.
- No fallback logic between old/new folders at serve time — the batch script is expected to fully populate the new folder before the switch happens.

## Architecture

```
IMAGE_FOLDER_PATH (existing, low-res, ~35 files)
        │
        │  scan_image_folder() [reused from src/ingestion.py]
        ▼
scripts/download_hq_images.py
        │  kagglehub download of images/{filename}
        │  from paramaggarwal/fashion-product-images-dataset
        ▼
hq_image_folder_path (new folder, high-res copies)
        │
        │  user manually edits .env: IMAGE_FOLDER_PATH -> hq_image_folder_path
        ▼
Existing routes (unchanged): GET /v1/images, GET /v1/images/{filename}
```

## Components

### `scripts/download_hq_images.py` (new)

- Reuses `scan_image_folder(settings.image_folder_path)` from `src/ingestion.py` to get the exact list of filenames currently in the app — this list *is* "images currently in my application," no separate CSV parsing needed.
- For each filename, downloads `images/{filename}` from the Kaggle dataset via `kagglehub.dataset_download(handle, path=...)` into `settings.hq_image_folder_path`.
- Skips a file if it already exists in the destination folder (idempotent — safe to re-run after adding more local images later).
- Wraps each per-file download in a narrow try/except (kagglehub/network errors specifically, not bare `except`); on failure, logs the filename and reason and continues to the next file — never aborts the batch.
- Prints an end-of-run summary: counts of downloaded / skipped (already present) / failed, and lists any failed filenames so the user knows which ones are still being served from the low-res folder.
- Sets `KAGGLE_USERNAME` / `KAGGLE_KEY` env vars from settings before the first kagglehub call (kagglehub reads credentials from the environment — no wrapper class, just env assignment at the top of `main()`).

### `src/config.py` (additions)

```python
hq_image_folder_path: str = ""
kaggle_username: str = ""
kaggle_key: str = ""
```

### `.env.example` (additions)

```
HQ_IMAGE_FOLDER_PATH=/path/to/hq_images
KAGGLE_USERNAME=
KAGGLE_KEY=
```

### Unchanged

- `src/main.py` — `list_images` / `serve_image` keep reading from `settings.image_folder_path` exactly as today. The switch to high-quality images happens by the user editing `IMAGE_FOLDER_PATH` in `.env` to point at the now-populated `hq_image_folder_path`, then restarting the server.
- `src/ingestion.py`, Pinecone vectors/metadata, embeddings — untouched.

## Data flow (one-time run)

1. User runs `venv/bin/python scripts/download_hq_images.py`.
2. Script scans `IMAGE_FOLDER_PATH`, gets filenames.
3. For each filename, downloads the matching high-res file from Kaggle into `HQ_IMAGE_FOLDER_PATH`, skipping ones already there.
4. Script prints summary.
5. User edits `.env`: `IMAGE_FOLDER_PATH=<value of HQ_IMAGE_FOLDER_PATH>`.
6. User restarts the backend server.
7. `/v1/images/{filename}` and the frontend now serve the high-quality files; search/ingestion behavior is unaffected since Pinecone metadata never stored a folder path, only the filename.

## Error handling

- Per-file download failure: log filename + error, continue (matches project's existing "log and skip, never crash" ingestion philosophy).
- Missing Kaggle credentials: fail fast at script start with a clear message (this is a system-boundary/config error, not a per-file transient failure).
- A file with no HQ match in the dataset is simply reported in the "failed" summary — the corresponding low-res file remains in the original folder, so nothing breaks if the user switches `IMAGE_FOLDER_PATH` before every file has a high-quality counterpart. (This is a known gap the user accepts for v1 — not solved by fallback logic, per the "no fallback" non-goal above.)

## Testing (manual, per project standard — no automated tests)

1. Run the script against the current ~35-image folder; confirm the summary's downloaded+skipped count matches the source folder's file count (or lists specific failures).
2. Spot-check one downloaded file: confirm its file size/pixel dimensions are larger than the low-res original.
3. Edit `.env` to point `IMAGE_FOLDER_PATH` at the new folder, restart the server.
4. Hit `GET /v1/images/{filename}` in Swagger for a known filename — confirm the high-quality file is returned.
5. Load the frontend search UI — confirm images render at higher quality with no broken images.
6. Run a search query — confirm results and metadata are unchanged (proving ingestion/Pinecone was unaffected).
7. Re-run the script a second time — confirm it reports everything as "skipped" (idempotency check).

## Open items to verify during implementation

- Exact in-dataset path convention for image files (assumed `images/{filename}` based on the known layout of this Kaggle dataset — confirm on the first real download call, adjust if kagglehub reports a different path).
- Confirm `kagglehub.dataset_download(handle, path=...)` is the correct call shape for a single-file fetch (vs. downloading to a specific target directory) once `kagglehub` is added to `requirements.txt` and installed in `venv`.
