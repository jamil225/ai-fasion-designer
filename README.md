# AI Fashion Designer

AI Fashion Designer extracts metadata from garment photos using computer vision, stores 1536-dimensional embeddings in Pinecone, and curates outfit combinations through a LangGraph ReAct agent. A multi-provider LLM gateway handles model calls with Vertex AI as primary and OpenAI as fallback. The web interface includes an outfit layout canvas, image lightbox, and shopping cart.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          REACT 19 FRONTEND                              │
│         Outfit Canvas · Image Lightbox · In-Memory Cart · OAuth         │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │ HTTP / REST (Port 8083)
┌───────────────────────────────────▼─────────────────────────────────────┐
│                       FASTAPI SERVICE LAYER                             │
│       Auth Middleware · OpenAI Moderation Guard · LangSmith Spans       │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼─────────────────────────────────────┐
│                       LANGGRAPH REACT AGENT                             │
│   check_required_fields ──► ask_user (HITL) ──► enrich_query ──► search │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼─────────────────────────────────────┐
│                        MULTI-PROVIDER GATEWAY                           │
│     Primary: Google Vertex AI (ADC) ──► Fallback: OpenAI gpt-5.6       │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼─────────────────────────────────────┐
│                          DATA & DB STORAGE                              │
│      Pinecone Vector DB (1536d) · Ingestion Log CSV · LangSmith      │
└─────────────────────────────────────────────────────────────────────────┘
```

### Core Components

- **LangGraph Agent (`src/agent/`)**: Executes a 5-tool sequence (`check_required_fields`, `ask_user`, `enrich_query`, `search_products`, `curate_outfits`). Pauses execution via `ask_user` when search criteria are incomplete. Reads grounded product data from state via `InjectedState`.
- **LLM Gateway (`src/llm_gateway/`)**: Routes text generation through a LiteLLM Router and agent calls through a LangChain fallback chain. Uses Google Vertex AI (`gemini-2.5-pro`) by default and switches to OpenAI (`gpt-5.6-terra`) if Vertex AI fails.
- **Guardrails (`src/agent/guardrails/`)**: Validates incoming user messages against the OpenAI Moderation API before invoking the agent. Managed via `config/guardrails.yaml`.
- **Ingestion Pipeline (`src/ingestion.py`)**: Computes SHA-256 file hashes to skip existing images. Extracts metadata with Gemini Vision, normalizes attribute values, builds OpenAI embeddings, and writes vectors to Pinecone.
- **Frontend UI (`frontend/`)**: Built with React 19 and Vite. Displays search results, outfit combinations, item details, and cart state.
- **GCP Deployment (`scripts/`)**: Deploys to a Google Compute Engine instance behind Nginx with Let's Encrypt SSL.

## Technical Specifications

| Layer | Component | Details |
|---|---|---|
| **Runtime** | Python, Node.js | Python 3.11+, Node.js 18+ |
| **Backend** | FastAPI, Uvicorn | Async route handlers running on port 8083 |
| **Agent Engine** | LangGraph | State graph with custom `FashionAgentState` |
| **LLM Gateway** | LiteLLM Router, LangChain | Primary: Vertex AI (`gemini-2.5-pro`), Fallback: OpenAI (`gpt-5.6-terra`) |
| **Vector DB** | Pinecone | Index `fashion-rag`, 1536 dimensions, Cosine similarity |
| **Embeddings** | OpenAI | Model `text-embedding-3-small` |
| **Frontend** | React 19, Vite | Standard CSS, proxy targets port 8083 |
| **Host** | GCP Compute Engine | `e2-small` instance in `asia-south1-a` (Mumbai), Ubuntu 24.04 |

## Local Setup

### 1. Environment Configuration

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Configure required variables in `.env`:

```env
PORT=8083
APP_API_KEY=your-app-api-key

USE_VERTEXAI=true
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_CLOUD_LOCATION=us-central1
OPENAI_API_KEY=your-openai-key

PINECONE_API_KEY=your-pinecone-key
PINECONE_INDEX_NAME=fashion-rag
IMAGE_FOLDER_PATH=/absolute/path/to/garment/images
```

### 2. Run Backend Service

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

PORT=8083 venv/bin/uvicorn src.main:app --port 8083 --reload
```

Interactive API documentation opens at `http://localhost:8083/docs`.

### 3. Run Frontend Interface

In a separate terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` in your browser. Vite proxies `/v1` requests to port 8083.

## Remote GCP Deployment

Deploy local edits to the remote GCP VM with one script:

```bash
./scripts/deploy-and-open.sh
```

This script:
1. Connects to instance `ai-fashion-designer` over SSH.
2. Executes `scripts/vm-update.sh` to pull code, build static frontend assets, and restart the backend service.
3. Checks `/v1/health` until the service responds.
4. Opens `https://8.234.93.21.nip.io/` in your browser.

## API Reference

| Path | Method | Auth | Description |
|---|---|---|---|
| `/v1/chat` | `POST` | Header | Conversational endpoint for outfit requests. Returns tool traces and combos. |
| `/v1/search/styled` | `POST` | Header | Direct outfit curation endpoint. |
| `/v1/search` | `POST` | Header | Vector search with filter support. |
| `/v1/ingest/start` | `POST` | Header | Scans `IMAGE_FOLDER_PATH` and updates Pinecone index. |
| `/v1/ingest/status/{job_id}` | `GET` | Header | Checks ingestion job status. |
| `/v1/pinecone/clear` | `DELETE` | Header | Clears all vectors from the target Pinecone index. |
| `/v1/images/{filename}` | `GET` | None | Serves local garment images. Sanitizes input paths. |
| `/v1/auth/google-login` | `POST` | None | Validates Google OAuth tokens. |
| `/v1/health` | `GET` | None | Returns status for service and Pinecone connectivity. |

## Repository Structure

```
ai-fashion-designer/
├── src/                        # Python backend service
│   ├── main.py                 # FastAPI application setup
│   ├── config.py               # Environment configuration via pydantic-settings
│   ├── ingestion.py            # Folder scanning and ingestion workflow
│   ├── ingestion_log.py        # CSV append logger for ingested vectors
│   ├── vision.py               # Gemini Vision metadata extraction
│   ├── merge.py                # Combines CSV vendor attributes with vision output
│   ├── taxonomy.py             # Normalizes fashion categories and colors
│   ├── embeddings.py           # Generates OpenAI embeddings
│   ├── pinecone_client.py     # Pinecone DB queries and upserts
│   ├── agent/                  # LangGraph agent implementation
│   │   ├── graph.py            # State graph structure
│   │   ├── tools.py            # Agent tool definitions
│   │   ├── routes.py           # Chat API endpoint and interrupt handling
│   │   ├── schemas.py          # State TypedDict and Pydantic models
│   │   ├── prompt_loader.py    # YAML prompt loader with caching
│   │   └── guardrails/         # Input moderation registry
│   └── llm_gateway/            # Dual-provider LLM abstraction
│       ├── gateway.py          # Gateway interface
│       ├── providers.py        # Router and fallback chain builders
│       └── callbacks.py        # Observability hooks
├── frontend/                   # React web application
│   ├── src/                    # UI components, canvas, and cart context
│   └── vite.config.js          # Vite configuration and proxy rules
├── scripts/                    # Automation scripts
│   ├── deploy-and-open.sh      # Local command to deploy to GCP VM
│   ├── vm-update.sh            # Remote VM update script
│   └── download_hq_images.py   # Kaggle dataset downloader
├── docs/                       # System documentation and diagrams
├── prompts/                    # Externalized YAML prompts
├── .github/workflows/          # GitHub Actions CI/CD workflows
├── AGENTS.md                   # Agent guidelines
└── CLAUDE.md                   # Development workflow and operating instructions
```
