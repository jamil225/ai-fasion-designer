# Design: Ingestion Log CSV

**Date:** 2026-08-08
**Status:** Approved, implementing directly (no plan/subagent flow for this one — small enough to build inline)

## Problem

Vision extraction (Gemini via `src/vision.py`) produces structured metadata per image during ingestion, which gets merged with CSV vendor data, normalized, and upserted to Pinecone. There's no persistent, human-readable record of what's been ingested over time — Pinecone itself isn't easy to skim. We want a running log of what ingestion has done so far.

## Decision

CSV, not JSON or Markdown — the merged metadata is mostly flat scalars with two small arrays (`colors`, `style_tags`), which fits a CSV row cleanly. Future scope (not built now): an option to also log the raw pre-merge vision output, for comparing what Gemini said vs. what ended up stored.

## Scope

- Captures the **final merged/normalized metadata** — the same data that gets upserted to Pinecone — not the raw vision output.
- **One persistent file**, appended to on every ingestion run (not one file per job).
- **Successes only** — one row per image that was actually upserted to Pinecone. Failures/skips are already tracked via the existing job status (`GET /v1/ingest/status/{job_id}`); no duplication here.

## Architecture

```
run_ingestion() [src/ingestion.py, per image, existing loop]
  vision -> merge -> normalize -> metadata dict [existing]
  embed -> upsert_vector(metadata) [existing]
  -> NEW: append_ingestion_log_row(settings.ingestion_log_csv_path, metadata)
  -> job_store counters increment [existing]
```

New module: `src/ingestion_log.py`
- `append_ingestion_log_row(csv_path: str, metadata: dict) -> None`
- Creates the file with a header row if it doesn't exist; appends one row per call otherwise.
- Wrapped in its own narrow `try/except OSError` at the call site in `run_ingestion()` — a logging failure must never fail the ingestion or mark an already-upserted image as failed (the vector is already safely in Pinecone by that point). Log a warning and continue.

## Config

`src/config.py` addition (Application Settings block, same pattern as `tryon_output_dir`):
```python
ingestion_log_csv_path: str = "ingestion_log.csv"
```
`.env.example` addition:
```
INGESTION_LOG_CSV_PATH=ingestion_log.csv
```

## Columns (16, in this order)

```
ingested_at, product_id, image_path, category, wear_type, colors, occasion,
style_tags, caption, pattern, fabric_hint, gender, product_display_name,
season, model_version, file_hash
```

`colors` and `style_tags` are lists in the metadata dict — joined with `;` in their CSV cell (e.g. `red;black`). All other columns are scalars pulled directly from the metadata dict by key. `raw_vision_output` is deliberately excluded — it's a long duplicate string of the other fields and would make rows unreadable.

## Testing (manual — no automated tests per project convention)

1. Run `/v1/ingest/start` via Swagger for a couple of images.
2. Confirm `ingestion_log.csv` is created at the configured path with a header row plus one row per successfully ingested image.
3. Run ingestion again with different (or the same, incremental-mode-skipped) images.
4. Confirm new rows are appended, existing rows untouched, header not duplicated.
5. Open the file and eyeball column values, confirming `colors`/`style_tags` are semicolon-joined and readable.
