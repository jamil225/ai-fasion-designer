# Vertex AI Migration — Design Spec

**Date:** 2026-06-01
**Branch:** `agentic-implementation`
**Status:** Implemented

---

## Problem

All Gemini API calls were routed through a direct `GEMINI_API_KEY` (Google AI Studio), billing the personal account. GCP offers a $300 free credit that can cover the same Gemini models via Vertex AI.

## Decision

Route all Gemini calls through **Vertex AI**. Keep OpenAI for embeddings (`text-embedding-3-small`) — switching would require a full Pinecone re-index (dimension change: 1536 → 768).

## Auth Model

**Application Default Credentials (ADC).** No JSON key file. User runs once:

```bash
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

The `google-genai` SDK and `langchain-google-vertexai` both pick up ADC automatically.

---

## Changes

### Config (`src/config.py`)

| Removed | Added |
|---|---|
| `gemini_api_key: str` | `google_cloud_project: str` |
| | `google_cloud_location: str = "us-central1"` |

Model name fields unchanged — Vertex AI serves the same Gemini model identifiers.

### Packages (`requirements.txt`)

| Removed | Added |
|---|---|
| `langchain-google-genai>=2.0,<3.0` | `langchain-google-vertexai>=2.0,<3.0` |
| | `google-cloud-aiplatform>=1.60` |
| `google-genai` (unpinned) | `google-genai>=1.0` (Vertex AI support requires 1.0+) |

### Agent graph (`src/agent/graph.py`)

`ChatGoogleGenerativeAI(model=..., google_api_key=...)` → `ChatVertexAI(model=..., project=..., location=...)`

### Five google-genai SDK modules

Each had `genai.Client(api_key=api_key)`. Changed to:

```python
_s = get_settings()
client = genai.Client(vertexai=True, project=_s.google_cloud_project, location=_s.google_cloud_location)
```

And `api_key: str` removed from function signatures.

| File | Function |
|---|---|
| `src/vision.py` | `extract_metadata()` |
| `src/merge.py` | `merge_product_data()` |
| `src/query_enrichment.py` | `enrich_query()` |
| `src/stylist_agent.py` | `curate_outfits()` |
| `src/virtual_trail_generator.py` | `generate_angles()` (standalone script) |

### Call-site updates (removed `api_key=settings.gemini_api_key`)

- `src/ingestion.py` — `extract_metadata()` and `merge_product_data()` calls
- `src/styled_search.py` — `enrich_query()` and `curate_outfits()` calls
- `src/agent/tools.py` — `enrich_query()` and `curate_outfits()` calls

---

## Out of Scope

- OpenAI embeddings / Pinecone re-index
- `src/agent/guardrails/openai_moderation.py` — uses OpenAI Moderation API (same rationale as embeddings)
- LangSmith config (unchanged)

---

## GCP Setup Checklist (one-time, user does manually)

1. Create or select a GCP project
2. Enable **Vertex AI API** in GCP Console
3. Run `gcloud auth application-default login`
4. Run `gcloud config set project YOUR_PROJECT_ID`
5. Set `GOOGLE_CLOUD_PROJECT=your-project-id` in `.env`
6. Optionally set `GOOGLE_CLOUD_LOCATION=us-central1` (default)

---

## Verification

```bash
pip install -r requirements.txt
python -c "from src.config import get_settings; s=get_settings(); print(s.google_cloud_project, s.google_cloud_location)"
uvicorn src.main:app --port 8083 &
sleep 3 && curl -s http://localhost:8083/v1/health
python -c "from src.agent.graph import AGENT; print('Agent loaded OK')"
kill %1
```
