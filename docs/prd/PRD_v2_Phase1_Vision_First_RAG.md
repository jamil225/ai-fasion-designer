# PRD v2: Phase I — Vision-First RAG for AI Fashion Designer

## Brief Summary

Build a Python FastAPI service that ingests garment images from a configured local folder, uses **Google Gemini Pro Vision** to auto-generate structured fashion metadata, embeds metadata as text vectors via **OpenAI text-embedding-3-small**, stores embeddings + metadata in **Pinecone**, and serves English natural-language retrieval such as "yellow and black look for wedding."

Phase I is optimized for fast delivery with clean, modular code. No CSV dependency — images are the only input.

---

## Development Philosophy

> **Write clean, modular code that works for 200 images today but doesn't break at 100K.**

- Functions do one thing well — easy to swap or upgrade later.
- No hardcoded limits or assumptions about data size.
- Clean interfaces between modules — so storage, processing, or serving can be replaced without rewriting.
- **No over-engineering in Phase I** — no async workers, caching layers, or distributed processing yet.
- Prioritize working software quickly. Scalability comes from good code structure, not premature infrastructure.

---

## Goals

- **Zero-CSV onboarding**: customers provide only images.
- **Vision-first metadata**: automatic extraction via Gemini Pro Vision.
- **Semantic retrieval**: text-to-image search with optional strict filters.
- **API-first**: FastAPI backend with Swagger UI for testing; ready for future web/mobile integration.

## Non-Goals (Phase I)

- Multilingual queries (English only).
- Outfit bundle / full-look composition.
- Continuous file-watcher ingestion.
- Separate relational database (Pinecone-only in Phase I).
- Frontend / UI (Swagger UI serves as testing interface).
- Automated unit / integration testing (manual testing via Swagger UI).
- Async / concurrent ingestion.
- Image serving via API endpoint.

---

## Users

| User | Actions |
|------|---------|
| End shopper | Sends English text queries, receives ranked garment results |
| Admin / operator | Triggers ingestion jobs, monitors status |

---

## Tech Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Backend Framework | FastAPI (Python) | API server, Swagger UI for testing |
| Vision Model | Google Gemini Pro Vision | Image → structured metadata extraction |
| Embedding Model | OpenAI text-embedding-3-small | Text → 1536-dimension vectors |
| Vector Database | Pinecone (cosine similarity) | Vector storage, semantic search, metadata filtering |
| Configuration | .env + pydantic-settings | API keys, app settings |
| Auth | API key middleware | Simple auth on all non-health endpoints |

---

## Architecture

### End-to-End Data Flow

```
INGESTION:
  Configured local folder
    → ingestion.py scans for image files
    → SHA-256 hash computed per image (skip duplicates)
    → vision.py sends image to Gemini Pro Vision → structured JSON metadata
    → taxonomy.py normalizes metadata to controlled enums
    → embeddings.py constructs text string from metadata → OpenAI embed → 1536d vector
    → pinecone_client.py upserts vector + metadata to Pinecone

SEARCH:
  User query (English text)
    → search.py receives query + optional filters
    → embeddings.py embeds query text → 1536d vector
    → pinecone_client.py queries Pinecone (cosine similarity + optional strict filters)
    → Return ranked results with product_id, image_path, score, matched attributes
```

### Project Structure

```
ai-fashion-designer/
├── src/
│   ├── main.py              # FastAPI app, route definitions, startup
│   ├── config.py             # pydantic-settings, env loading, defaults
│   ├── auth.py               # API key validation middleware
│   ├── vision.py             # Gemini Pro Vision metadata extraction
│   ├── embeddings.py         # OpenAI text-embedding-3-small client
│   ├── pinecone_client.py    # Pinecone init, upsert, query operations
│   ├── ingestion.py          # Folder scanning, dedup, orchestration
│   ├── search.py             # Query processing, filtering, ranking
│   ├── taxonomy.py           # Controlled enums + normalization logic
│   └── schemas.py            # Pydantic request/response models
├── tests/                    # Phase II: automated tests
│   ├── test_ingestion.py
│   ├── test_search.py
│   └── test_vision.py
├── .env                      # API keys and config (gitignored)
├── .env.example              # Template with placeholder values
├── requirements.txt
└── README.md
```

---

## Public APIs

### POST `/v1/ingest/start`

Trigger batch ingestion from the configured image folder.

**Request:**
```json
{
  "mode": "full"              // "full" = process all images, "incremental" = skip already ingested
}
```

**Response (202):**
```json
{
  "job_id": "uuid",
  "queued_count": 150,
  "status": "processing"
}
```

**Notes:**
- Image folder path is read from server configuration (`.env`), NOT from the request body (security: prevents path traversal).
- Ingestion runs synchronously in Phase I — the response returns after processing completes.
- `mode: "incremental"` uses SHA-256 file hash to skip already-ingested images.

---

### GET `/v1/ingest/status/{job_id}`

**Response (200):**
```json
{
  "job_id": "uuid",
  "status": "processing | completed | failed",
  "total": 150,
  "processed": 87,
  "failed": 2,
  "failed_items": [
    {"filename": "img_042.jpg", "error": "Vision API timeout"}
  ],
  "started_at": "2026-02-27T10:00:00Z",
  "finished_at": null
}
```

**Notes:**
- `failed_items` contains filename only — no full file paths exposed in API responses.
- Job state is held in memory in Phase I (lost on server restart).

---

### POST `/v1/search`

**Request:**
```json
{
  "query": "yellow and black look for wedding",
  "top_k": 10,
  "strict_mode": false,
  "filters": {
    "colors": ["yellow", "black"],
    "occasion": "wedding",
    "category": ["dress", "saree"]
  }
}
```

**Response (200):**
```json
{
  "results": [
    {
      "product_id": "uuid",
      "image_path": "/images/garment_01.jpg",
      "score": 0.92,
      "matched_attributes": {
        "colors": ["yellow", "black"],
        "occasion": "wedding",
        "category": "saree"
      },
      "caption": "A stuning yellow and black saree perfect for a wedding",
      "style_tags": ["embroidered", "traditional", "elegant"]
    }
  ],
  "applied_filters": {"colors": ["yellow", "black"], "occasion": "wedding"},
  "total_results": 5,
  "latency_ms": 340
}
```

**Notes:**
- `strict_mode: false` (default) — pure semantic search, filters ignored, results ranked by cosine similarity across all vectors.
- `strict_mode: true` — Pinecone metadata filters applied before similarity search. Only garments matching ALL filter criteria are candidates.
- Zero results returns empty array, does not fall back to soft mode (predictable behavior).

---

### GET `/v1/health`

**Response (200):**
```json
{
  "status": "healthy",
  "pinecone": "connected",
  "version": "0.1.0"
}
```

**Notes:**
- Only endpoint that does NOT require API key authentication.

---

## Search Logic

### Soft Mode (default)

Pure semantic search. User query is embedded and compared against all vectors via cosine similarity. Best for vague queries like "something elegant for a party."

### Strict Mode

Two-step process:
1. **Filter** — Pinecone metadata filters remove non-matching garments before search (like a SQL `WHERE` clause).
2. **Rank** — Cosine similarity runs on the filtered set only.

Pinecone filter syntax used internally:
```python
{
    "colors": {"$in": ["yellow", "black"]},    # garment has any of these colors
    "occasion": {"$eq": "wedding"},             # exact match
    "category": {"$in": ["dress", "saree"]}     # any of these categories
}
```

| Scenario | Recommended Mode |
|----------|-----------------|
| "something elegant for a party" | Soft — vague, let semantics decide |
| "show me only red sarees for wedding" | Strict — user wants exact matches |
| No filters provided + strict mode | Behaves same as soft mode |

---

## Vision Metadata Extraction

### Gemini Pro Vision Prompt (per image)

```
Analyze this garment image and return a JSON object with:
- category: one of [dress, saree, shirt, blazer, trousers, skirt, shoes, jacket, kurta, lehenga, gown, top, other]
- colors: array of dominant colors from [red, blue, green, yellow, black, white, pink, purple, orange, gold, silver, beige, brown, maroon, navy, grey, multicolor]
- occasion: one of [wedding, party, casual, formal, festive, office, traditional]
- style_tags: array of 3-5 descriptive tags (e.g. embroidered, floral, silk, vintage, modern)
- caption: one-line description of the garment Focus on the clothes not on the model wearing it details. 

Return ONLY valid JSON, no other text.
```

### Phase I Metadata Fields (Essential)

| Field | Type | Source |
|-------|------|--------|
| `category` | string | Gemini → normalized to taxonomy |
| `colors` | string[] | Gemini → normalized to taxonomy |
| `occasion` | string | Gemini → normalized to taxonomy |
| `style_tags` | string[] | Gemini raw output |
| `caption` | string | Gemini raw output |

### Phase II Extended Fields (Deferred)

| Field | Type | Notes |
|-------|------|-------|
| `fabric` | string | e.g. silk, cotton, polyester |
| `pattern` | string | solid, striped, floral, printed |
| `fit` | string | slim, loose, regular |
| `gender` | string | men, women, unisex |

---

## Metadata Stored in Pinecone (per vector)

```json
{
  "product_id": "uuid",
  "image_path": "/images/garment_01.jpg",
  "file_hash": "sha256_abc123",
  "category": "saree",
  "colors": ["yellow", "black"],
  "occasion": "wedding",
  "style_tags": ["embroidered", "traditional", "elegant"],
  "caption": "A yellow and black embroidered saree for weddings",
  "raw_vision_output": "{...original Gemini response...}",
  "model_version": "gemini-pro-vision",
  "ingested_at": "2026-02-27T10:00:00Z"
}
```

**Notes:**
- `raw_vision_output` preserved for traceability and debugging.
- `file_hash` used for duplicate detection during incremental ingestion.

---

## Embedding Text Construction

Metadata fields are combined into a single text string before embedding:

```
"{category} in {colors joined} colors for {occasion} occasion. {style_tags joined}. {caption}"
```

Example:
```
"saree in yellow and black colors for wedding occasion. embroidered, traditional, elegant. A yellow and black embroidered saree for weddings."
```

This ensures the vector captures category, colors, occasion, tags, and description semantically. Both ingestion and search use the same OpenAI embedding model, so vectors live in the same space.

---

## Taxonomy and Normalization

Controlled enums are hardcoded in `taxonomy.py` and version-controlled:

### Categories
`dress, saree, shirt, blazer, trousers, skirt, shoes, jacket, kurta, lehenga, gown, top, other`

### Occasions
`wedding, party, casual, formal, festive, office, traditional`

### Colors
`red, blue, green, yellow, black, white, pink, purple, orange, gold, silver, beige, brown, maroon, navy, grey, multicolor`

### Normalization Rules
- Gemini output is mapped to the closest canonical value.
- Synonyms normalized before upsert (e.g. "crimson" → "red", "ivory" → "white").
- Unrecognized values mapped to closest match or `other`.
- Raw Gemini output preserved in `raw_vision_output` for traceability.

---

## Duplicate Detection

- On ingestion, each image file is hashed with **SHA-256**.
- Hash is checked against existing Pinecone metadata (`file_hash` field).
- If hash exists, image is **skipped** (not re-processed).
- **Product ID** is a separate **UUID** — not derived from the hash.
- This prevents exact file re-ingestion while keeping product IDs always unique.

---

## Pinecone Configuration

| Setting | Value |
|---------|-------|
| Index name | `fashion-rag` (configurable in .env) |
| Dimensions | 1536 |
| Metric | Cosine |
| Cloud/Region | Configurable in .env |

---

## Configuration (.env)

```
# External API Keys
GEMINI_API_KEY=your-gemini-api-key
OPENAI_API_KEY=your-openai-api-key
PINECONE_API_KEY=your-pinecone-api-key

# Pinecone Settings
PINECONE_INDEX_NAME=fashion-rag
PINECONE_ENVIRONMENT=us-east-1

# Application Settings
APP_API_KEY=your-app-api-key
IMAGE_FOLDER_PATH=/path/to/images
DEFAULT_TOP_K=10
```

A `.env.example` file with placeholder values is committed to the repository for onboarding.

---

## Security

- **API key auth** on all endpoints except `/v1/health`.
- API key validated via `X-API-Key` header, checked in middleware.
- Invalid or missing key returns `401 Unauthorized`.
- All API keys stored in `.env` file (gitignored), never hardcoded.
- **Image folder path** read from server config only — never accepted from API requests (prevents path traversal).
- **No full file paths** exposed in API error responses (filename only in failed_items).
- No PII collected or stored in Phase I.

---

## Error Handling

### Retry Strategy (Phase I — Simple)
- **3 retries** with exponential backoff (1s, 2s, 4s) for transient failures from Gemini Vision API and Pinecone.
- After 3 failures, mark image as **failed** with error reason and continue to next image.
- Failed items logged and visible via ingestion status endpoint.
- No dead-letter queue or replay mechanism in Phase I.

### Error Cases
| Scenario | Behavior |
|----------|----------|
| Corrupt/unreadable image | Marked failed, ingestion continues |
| Gemini Vision API timeout | Retried 3x, then marked failed |
| Pinecone upsert failure | Retried 3x, then marked failed |
| Invalid Gemini response (bad JSON) | Marked failed with parse error |

---

## Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| Initial test scale | 100–200 images |
| Production scale | 10K–100K+ images (code must not assume small scale) |
| Search latency | p95 < 2 seconds |
| Ingestion (Phase I) | Synchronous sequential |
| Auth | API key on non-health endpoints |
| Testing | Manual via Swagger UI (Phase I) |

### Observability
- Structured logs with `request_id`, `job_id`, `product_id`.
- Log: ingestion throughput, failure reasons, search latency, zero-result queries.

---

## Testing Strategy (Phase I)

### Manual Testing via Swagger UI
- FastAPI auto-generates interactive API docs at `/docs`.
- All endpoints testable directly in browser.
- This is the primary testing interface for Phase I.

### Manual Acceptance Criteria
1. Ingest a folder of sample images — all succeed or fail gracefully.
2. Each ingested item exists in Pinecone with all required metadata fields.
3. Search "yellow and black look for wedding" returns relevant garments in top-5.
4. Strict mode correctly filters by color/occasion/category.
5. Duplicate image re-ingestion is skipped.
6. Corrupt image doesn't crash the service.
7. Health endpoint returns connected status.
8. Unauthenticated requests return 401.

---

## Milestones

1. **Service skeleton** — FastAPI app, config loading, auth middleware, health endpoint.
2. **Ingestion API** — Folder scanner, dedup logic, ingestion orchestration, status tracking.
3. **Vision pipeline** — Gemini Pro Vision integration, structured output parsing, taxonomy normalization.
4. **Embedding + storage** — Embedding text construction, OpenAI embedding, Pinecone upsert.
5. **Search API** — Query embedding, Pinecone query, soft/strict modes, response formatting.
6. **Manual testing** — End-to-end validation via Swagger UI against sample images.

---

## Phase II Roadmap

| Item | Description |
|------|-------------|
| Extended metadata | Add fabric, pattern, fit, gender fields to vision extraction |
| PostgreSQL | Add for: (1) ingestion job persistence, (2) dedup hash index, (3) failed record replay queue |
| Async ingestion | Concurrent processing with background jobs and status polling |
| Production retry | Dead-letter queue, configurable retry policies |
| Image serving API | `GET /v1/images/{product_id}` endpoint to serve images |
| Hybrid search | BM25 + vector search, reranking, result caching |
| Automated testing | Unit tests, integration tests, relevance evaluation suite |
| Metadata correction | Admin interface to fix/override vision-extracted metadata |
| Object storage | Move from local folder to S3/GCS for production image storage |
| Retrieval optimization | Query expansion, synonym handling, relevance tuning |

---

## Assumptions

- Google Gemini Pro Vision, OpenAI, and Pinecone API keys are available and configured.
- Pinecone is the only operational store in Phase I (no relational DB).
- Raw images remain in local folder, referenced by path.
- English-only query support.
- Filename is identifier-only — not a source of semantic metadata.
- Pinecone free tier is sufficient for Phase I scale.
- No frontend required — Swagger UI is the testing interface.
- Job state is held in memory — acceptable for Phase I (lost on restart).

---

## Decision Log

| # | Decision | Choice | Alternatives Considered | Rationale |
|---|----------|--------|------------------------|-----------|
| 1 | Data source | Local image folder | Cloud storage, URL list | Fast onboarding, minimal setup |
| 2 | Metadata generation | Gemini Pro Vision (vision-first) | CSV/manual, custom CNN classifiers, CLIP | Modern production pattern, one API call replaces 5+ custom models |
| 3 | Embedding model | OpenAI text-embedding-3-small | Google text-embedding-004, sentence-transformers (local) | Proven retrieval quality, 1536d, widely used |
| 4 | Embedding strategy | Text-only (vision → text → embed) | CLIP direct, hybrid text+CLIP | Both query and document in same text embedding space; rich metadata enables filters; debuggable |
| 5 | Vector database | Pinecone (cosine similarity) | Weaviate, Qdrant, pgvector | Managed service, free tier sufficient, strong filter support |
| 6 | Similarity metric | Cosine | Dot product, Euclidean | Standard for text embeddings, normalizes vector length |
| 7 | Storage strategy | Pinecone-only (Phase I) | Pinecone + SQLite, Pinecone + PostgreSQL | Minimal infra; PostgreSQL planned for Phase II |
| 8 | Image serving | Local file paths (modular for future API) | API serving, both | Simplest for Phase I; code structured for easy swap |
| 9 | Metadata fields | 5 essential fields (Phase I) | 8 extended fields | YAGNI — extended fields deferred to Phase II |
| 10 | Taxonomy | Hardcoded config file | Dynamic file, no enforcement | Version-controlled, simple, consistent |
| 11 | Duplicate detection | SHA-256 file hash, skip duplicates | Overwrite/upsert, no handling | Prevents wasted API calls on re-ingestion |
| 12 | Product ID | UUID (separate from file hash) | Hash-based, filename-based | Guaranteed unique, no false positive dedup risk |
| 13 | Retry strategy | Simple 3x exponential backoff | Dead-letter queue, persistent retry | Phase I simplicity; production retry in Phase II |
| 14 | Ingestion model | Synchronous sequential | Async concurrent, background jobs | Simple, debuggable; async deferred to Phase II |
| 15 | Framework | FastAPI | Flask, Django | Auto Swagger UI, async-ready, Pydantic integration |
| 16 | Configuration | .env + pydantic-settings | Plain env vars, config service | Standard Python pattern, typed settings |
| 17 | Project structure | Flat modular (src/) | Layered packages | Right-sized for Phase I; clean enough to grow |
| 18 | Ingestion folder | From config only (not API input) | API parameter | Security: prevents path traversal attacks |
| 19 | Search response | No caption in response | Caption included | Reduces response size; caption used internally for embedding only |
| 20 | Testing | Manual via Swagger UI | Unit/integration tests | Phase I speed; automated testing in Phase II |
| 21 | Language | English only | Multilingual | Scoped for Phase I delivery |
| 22 | Output | Individual garments | Outfit bundles | Bundle composition is Phase II+ |
