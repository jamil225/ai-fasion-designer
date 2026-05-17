# AI Fashion Designer 👗✨

Welcome to **AI Fashion Designer**! Imagine having a personal AI stylist at your fingertips. Instead of just searching for individual items, you can tell the AI Fashion Designer exactly what you're looking for, and it will thoughtfully curate a cohesive, top-to-bottom outfit for you. 

Whether you need a complete look for a summer wedding or a sharp casual outfit for the weekend, it acts just like a human fashion stylist—using its deep knowledge to match top and bottom wear perfectly into one unified design.

## What it does

1. **Look & Learn**: Feeds garment images to Google Gemini Pro Vision to automatically extract structured fashion metadata (category, color, occasion, style tags).
2. **Remember**: Embeds this metadata using OpenAI's `text-embedding-3-small` and stores it into Pinecone.
3. **Design & Find**: You describe the vibe or occasion. The system does the heavy lifting, acting as your personal stylist to retrieve matching pieces that create the perfect overall look.

All of this works without you ever touching a CSV file. You're welcome.

## Tech Stack

**Backend:**
- **FastAPI** (Python 3.11+) for the speedy API and Swagger UI.
- **Google Gemini Pro Vision** for analyzing garment images.
- **OpenAI text-embedding-3-small** for generating 1536-dimensional vectors.
- **Pinecone** for vector storage and semantic search.

**Frontend:**
- **React 19** with Vite for a responsive, modern UI.
- **Vanilla CSS** for styling.

## Quick Start (5 minutes)

### Prerequisites
- Python 3.11+
- Node.js 18+
- API keys for:
  - Google Gemini Pro Vision
  - OpenAI (text-embedding-3-small)
  - Pinecone
  - (Create a custom app API key for authentication)

### Backend Setup

1. **Clone and navigate to the project:**
   ```bash
   cd /path/to/ai-fashion-designer
   ```

2. **Create and activate virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env and fill in your API keys and settings
   ```

   **Required environment variables:**
   ```env
   GEMINI_API_KEY=your-gemini-api-key
   OPENAI_API_KEY=your-openai-api-key
   PINECONE_API_KEY=your-pinecone-api-key
   PINECONE_INDEX_NAME=fashion-rag
   PINECONE_ENVIRONMENT=us-east-1
   APP_API_KEY=your-custom-app-api-key
   IMAGE_FOLDER_PATH=/path/to/garment/images
   DEFAULT_TOP_K=10
   ```

5. **Run the FastAPI server:**
   ```bash
   uvicorn src.main:app --reload
   ```
   
   Backend will be available at: `http://localhost:8000`
   - API Swagger UI: `http://localhost:8000/docs`
   - ReDoc: `http://localhost:8000/redoc`

### Frontend Setup

1. **Navigate to frontend directory:**
   ```bash
   cd frontend
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Configure frontend API endpoint:**
   ```bash
   # Check frontend/.env, default is http://localhost:8000
   cat .env
   ```

4. **Start the development server:**
   ```bash
   npm run dev
   ```
   
   Frontend will be available at: `http://localhost:5173`

### Full Application Access

Once both backend and frontend are running:
- **Interactive UI**: `http://localhost:5173` — search, browse, and refine results
- **API Documentation**: `http://localhost:8000/docs` — test endpoints directly with Swagger UI
- **Health Check**: `http://localhost:8000/v1/health` — verify system status

## API Endpoints

### Ingestion
- **`POST /v1/ingest/start`** — Kick off image ingestion from configured folder
- **`GET /v1/ingest/status/{job_id}`** — Poll ingestion job status
- **`DELETE /v1/pinecone/clear`** — Clear all vectors from index (for testing)

### Search
- **`POST /v1/search`** — Semantic search with soft/strict filtering modes
- **`POST /v1/search/styled`** — AI-powered outfit recommendation (two-agent pipeline)
- **`GET /v1/images`** — List available images
- **`GET /v1/images/{filename}`** — Retrieve a specific image

### Health & Status
- **`GET /v1/health`** — Check system status and Pinecone connectivity
- **`GET /`** — Redirect to frontend

## Development Workflow

### Testing the API
1. Start the backend: `uvicorn src.main:app --reload`
2. Open Swagger UI: `http://localhost:8000/docs`
3. Test endpoints directly (auth required for all except `/v1/health`)

### Building for Production
**Backend:**
```bash
# No Docker/build step needed for Phase I
# Deploy src/ directory with Python 3.11+ runtime
```

**Frontend:**
```bash
cd frontend
npm run build
# Output in frontend/dist/ — ready to serve as static files
```

## Project Structure

```
ai-fashion-designer/
├── src/                        # Backend (Python)
│   ├── main.py                # FastAPI app & routes
│   ├── config.py              # Configuration & env loading
│   ├── auth.py                # API key authentication
│   ├── ingestion.py           # Image scanning & deduplication
│   ├── vision.py              # Gemini Pro Vision integration
│   ├── embeddings.py          # OpenAI text embedding
│   ├── pinecone_client.py     # Pinecone vector operations
│   ├── search.py              # Semantic search logic
│   ├── styled_search.py       # AI outfit recommendation
│   ├── taxonomy.py            # Controlled enums & normalization
│   ├── schemas.py             # Pydantic request/response models
│   ├── auth_routes.py         # Authentication routes
│   └── static/                # Served static frontend
├── frontend/                   # Frontend (React + Vite)
│   ├── src/                   # React components
│   ├── public/                # Static assets
│   ├── index.html             # Entry point
│   ├── vite.config.js         # Vite configuration
│   └── package.json           # Node dependencies
├── docs/                       # Architecture diagrams & docs
├── .env.example               # Environment template
├── requirements.txt           # Python dependencies
├── PRD_v2_Phase1_Vision_First_RAG.md  # Requirements document
└── CLAUDE.md                  # Development guidelines
```

## Troubleshooting

### Backend won't start
- Check Python version: `python --version` (requires 3.11+)
- Verify all dependencies: `pip list | grep -E 'fastapi|pydantic|google-genai|openai|pinecone'`
- Check `.env` file exists and all required keys are set

### Frontend won't connect to backend
- Ensure backend is running on `localhost:8000`
- Check `frontend/.env` for correct API endpoint
- Clear browser cache (Ctrl+Shift+Delete or Cmd+Shift+Delete)

### Pinecone connection fails
- Verify `PINECONE_API_KEY` is correct in `.env`
- Check `PINECONE_INDEX_NAME` matches your Pinecone index
- Ensure your Pinecone project has the index created

### API returns 401 Unauthorized
- Check `X-API-Key` header is set to your `APP_API_KEY` value
- `/v1/health` endpoint does NOT require authentication

## What's Committed to GitHub

**Committed Code (8 commits):**
- ✅ Full backend implementation (~2,200 lines of Python)
- ✅ Frontend UI with React + Vite
- ✅ Configuration and authentication
- ✅ Vision, embedding, and search pipelines
- ✅ Architecture diagrams and PRD documentation
- ✅ Test images for quick validation

**Not Committed (local development only):**
- `.env` (contains API keys) — use `.env.example` template
- `venv/` directory (Python virtual environment)
- `frontend/node_modules/` (Node dependencies)
- `frontend/dist/` (Build output)
- `.DS_Store` (macOS system files)

## Roadmap

This is **Phase I** — optimized for clean, modular code and fast delivery. We're keeping it simple and scalable without over-engineering.

**Phase II plans** (not yet implemented):
- Extended metadata extraction
- PostgreSQL database integration
- Outfit bundle / full-look composition
- Batch processing and async pipelines
- Advanced caching strategies

---
*Built with ❤️, Python, and a whole lot of vectors.*
