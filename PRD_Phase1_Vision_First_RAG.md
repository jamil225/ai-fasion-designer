# PRD: Phase I Vision-First RAG for AI Fashion Designer (English Only)

## Brief Summary
Build a Python API service that ingests garment images from a local folder, uses Google Nano Banana Vision API to auto-generate fashion metadata, stores embeddings + metadata in Pinecone, and serves English natural-language retrieval such as "yellow and black look for wedding."  
Phase I is optimized for minimal onboarding for customers who do not have CSV/catalog metadata.

## Goals
- Zero-CSV onboarding: customers provide only images.
- Automatic metadata extraction via vision model.
- High-quality semantic retrieval with optional strict filters.
- API-first backend for later web/mobile integration.

## Non-Goals (Phase I)
- Multilingual queries (English only).
- Outfit bundle composition engine.
- Continuous watcher ingestion.
- Separate canonical SQL store (per your choice: Pinecone-only metadata).

## Users
- End shoppers searching by style intent.
- Admin/operator triggering ingestion and reindex jobs.

## Core Product Behavior
1. User sends English query (example: "yellow and black look for wedding").
2. System embeds query, retrieves top garments from Pinecone.
3. Optional strict filters enforce hard constraints (color, occasion, category).
4. API returns ranked individual garments with confidence and matched attributes.

## Metadata Storage Strategy (Final)
- Use Google Nano Banana Vision API for automatic tagging/captioning.
- Store in Pinecone:
  - Vector embedding.
  - `product_id`.
  - `image_path`.
  - Auto metadata (`category`, `colors`, `occasion`, `style_tags`, `caption`).
  - Processing metadata (`model_version`, `ingested_at`, `confidence`).
- Raw image files remain in local folder storage.
- Do not rely on image filename for semantics; keep it only as identifier/reference.

## Public APIs / Interfaces

### POST `/v1/ingest/start`
- Trigger batch ingestion from folder.
- Input:
  - `folder_path: string`
  - `mode: "full" | "incremental"`
- Output:
  - `job_id`
  - `queued_count`
  - `status`

### GET `/v1/ingest/status/{job_id}`
- Returns `total`, `processed`, `failed`, `status`, `started_at`, `finished_at`.

### POST `/v1/search`
- Input:
  - `query: string` (English)
  - `top_k?: int` (default 10)
  - `strict_mode?: boolean` (default false)
  - `filters?: { colors?: string[], occasion?: string, category?: string[] }`
- Output:
  - `results[]` with `product_id`, `image_path`, `score`, `matched_attributes`, `caption`
  - `applied_filters`
  - `latency_ms`

### GET `/v1/health`
- Liveness/readiness check.

## Architecture (Phase I)
1. Ingestion API receives local folder path.
2. Service enumerates images and creates ingestion tasks.
3. For each image:
   - Call Google Nano Banana Vision API.
   - Normalize tags to controlled taxonomy.
   - Build embedding text from normalized metadata + caption.
   - Generate embedding.
   - Upsert vector + metadata to Pinecone.
4. Search API performs semantic retrieval + optional strict filtering.
5. Return ranked garments.

## Taxonomy and Normalization
- Maintain controlled enums for:
  - `category` (dress, saree, shirt, blazer, shoes, etc.)
  - `occasion` (wedding, party, casual, formal, festive)
  - `colors` (normalized base color set)
- Keep raw vision output in `raw_tags` for traceability.
- Normalize synonyms to canonical tags before upsert.

## Non-Functional Requirements
- Initial scale: 100–200 images.
- Search latency target: p95 < 2s.
- Auth: API key on non-health endpoints.
- Reliability:
  - Retry transient model/Pinecone failures.
  - Mark failed records with reason for replay.
- Observability:
  - Structured logs with `request_id`, `job_id`, `product_id`.
  - Metrics: ingestion throughput, failure rate, search latency, zero-result rate.

## Testing and Acceptance Criteria

### Functional Tests
1. Ingest folder of sample images successfully.
2. Each ingested item appears in Pinecone with required metadata fields.
3. Search returns top-k ranked garments with valid references.

### Quality Tests
1. Query: "yellow and black look for wedding" returns relevant wedding garments in top-5.
2. Strict mode enforces hard filters for requested colors/occasion.
3. Soft mode returns semantically relevant alternatives if exact matches are scarce.

### Failure Tests
1. Corrupt image file -> marked failed, no service crash.
2. Vision API timeout -> retried then failed with reason.
3. Pinecone outage -> retried with backoff, job status preserved.

## Security and Compliance
- API keys stored in environment variables/secret manager.
- No PII required for Phase I.
- Restrict exposed image paths to safe mapped outputs.

## Milestones
1. Service skeleton (FastAPI), auth middleware, health endpoint.
2. Ingestion job API + folder scanner.
3. Vision metadata extractor + normalization pipeline.
4. Embedding + Pinecone upsert.
5. Search API with strict/soft modes.
6. Test suite + baseline relevance evaluation.

## Phase II Preview
- Retrieval optimization (hybrid BM25 + vector, reranking, caching).
- Metadata correction interface.
- Scale tuning and optional move from local folder to object storage.

## Assumptions and Defaults
- Pinecone is the only metadata/vector operational store in Phase I.
- English-only query support.
- Google Nano Banana Vision API and embedding provider keys are available.
- Raw images remain local for Phase I and are referenced by path.
- Filename is identifier-only, not semantic metadata source.

## Decision Log
1. Data source: local image folder (chosen for fast onboarding).
2. Metadata generation: vision-first automation (chosen over CSV/manual for customer simplicity).
3. Storage: Pinecone-only metadata + vectors (chosen for minimal infra).
4. Retrieval mode: soft relevance + optional strict filters.
5. Output: top individual garments, not outfit bundles.
6. Language scope: English only.
7. Backend/auth: Python APIs with API key auth.
