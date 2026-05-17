import logging
import os
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from src.agent.routes import router as chat_router
from src.auth import verify_auth
from src.auth_routes import router as auth_router
from src.config import Settings, get_settings
from src.ingestion import get_job_status, run_ingestion
from src.pinecone_client import check_connection, delete_all_vectors, init_pinecone
from src.schemas import (
    HealthResponse,
    IngestRequest,
    IngestResponse,
    IngestStatus,
    IngestStatusResponse,
    SearchRequest,
    SearchResponse,
    StyledSearchRequest,
    StyledSearchResponse,
)
from src.search import run_search
from src.styled_search import run_styled_search

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

# Activate LangSmith tracing — must set os.environ BEFORE langsmith is imported
# by any route handler, so we do it here at module load time.
def _configure_langsmith() -> None:
    from src.config import get_settings
    s = get_settings()
    if s.langchain_tracing_v2 and s.langchain_api_key:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = s.langchain_api_key
        os.environ["LANGCHAIN_PROJECT"] = s.langchain_project
        logger.info("LangSmith tracing ON — project: %s", s.langchain_project)
    else:
        logger.info("LangSmith tracing OFF (set LANGCHAIN_TRACING_V2=true + LANGCHAIN_API_KEY to enable)")

_configure_langsmith()

app = FastAPI(
    title="AI Fashion Designer",
    description="Vision-first RAG for fashion garment search",
    version="0.1.0",
)

_static_dir = Path(__file__).parent / "static"
_static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")
app.include_router(auth_router)
app.include_router(chat_router)


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/static/index.html")


_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


@app.get("/v1/images", dependencies=[Depends(verify_auth)])
async def list_images(settings: Settings = Depends(get_settings)) -> dict:
    folder = Path(settings.image_folder_path)
    if not folder.exists():
        return {"filenames": []}
    filenames = sorted(
        p.name for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in _IMAGE_EXTENSIONS
    )
    return {"filenames": filenames}


@app.get("/v1/images/{filename}", dependencies=[Depends(verify_auth)])
async def serve_image(
    filename: str, settings: Settings = Depends(get_settings)
) -> FileResponse:
    image_path = Path(settings.image_folder_path) / filename
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(image_path)


@app.get("/v1/health", response_model=HealthResponse)
async def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    pinecone_status = "not_configured"
    if settings.pinecone_api_key and settings.pinecone_index_name:
        connected = check_connection(
            settings.pinecone_api_key, settings.pinecone_index_name
        )
        pinecone_status = "connected" if connected else "disconnected"

    return HealthResponse(
        status="healthy",
        pinecone=pinecone_status,
        version="0.1.0",
    )


@app.post(
    "/v1/ingest/start",
    response_model=IngestResponse,
    dependencies=[Depends(verify_auth)],
)
async def ingest_start(
    request: IngestRequest,
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    job_id = run_ingestion(settings, request.mode)
    job = get_job_status(job_id)

    response = IngestResponse(
        job_id=job_id,
        queued_count=job["total"],
        status=job["status"],
    )

    # 202 if completed/processing, 500 if all images failed
    if job["status"] == IngestStatus.FAILED:
        return JSONResponse(status_code=500, content=response.model_dump())

    return JSONResponse(status_code=202, content=response.model_dump())


@app.get(
    "/v1/ingest/status/{job_id}",
    response_model=IngestStatusResponse,
    dependencies=[Depends(verify_auth)],
)
async def ingest_status(job_id: str) -> IngestStatusResponse:
    job = get_job_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return IngestStatusResponse(**job)


@app.delete(
    "/v1/pinecone/clear",
    dependencies=[Depends(verify_auth)],
)
async def clear_pinecone_index(
    settings: Settings = Depends(get_settings),
) -> dict:
    init_pinecone(settings.pinecone_api_key, settings.pinecone_index_name)
    delete_all_vectors()
    return {"status": "cleared", "message": "All vectors deleted from Pinecone index"}


@app.post(
    "/v1/search",
    response_model=SearchResponse,
    dependencies=[Depends(verify_auth)],
)
async def search(
    request: SearchRequest,
    settings: Settings = Depends(get_settings),
) -> SearchResponse:
    return run_search(
        openai_api_key=settings.openai_api_key,
        pinecone_api_key=settings.pinecone_api_key,
        pinecone_index_name=settings.pinecone_index_name,
        best_match_score_threshold=settings.best_match_score_threshold,
        request=request,
    )


@app.post(
    "/v1/search/styled",
    response_model=StyledSearchResponse,
    dependencies=[Depends(verify_auth)],
)
async def styled_search(
    request: StyledSearchRequest,
    settings: Settings = Depends(get_settings),
) -> StyledSearchResponse:
    return run_styled_search(settings=settings, request=request)
