import hashlib
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from src.config import Settings
from src.csv_loader import get_csv_row, load_csv_lookup
from src.embeddings import build_embedding_text, generate_embedding
from src.merge import merge_product_data
from src.pinecone_client import hash_exists, init_pinecone, upsert_vector
from src.schemas import FailedItem, IngestMode, IngestStatus
from src.taxonomy import normalize_vision_output
from src.vision import extract_metadata

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}

# In-memory job store (lost on restart — acceptable for Phase I)
job_store: dict[str, dict] = {}


def compute_file_hash(file_path: Path) -> str:
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def scan_image_folder(folder_path: str) -> list[Path]:
    folder = Path(folder_path)
    if not folder.exists() or not folder.is_dir():
        raise FileNotFoundError(f"Image folder not found: {folder_path}")

    images = [
        f for f in sorted(folder.iterdir())
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    logger.info("Found %d images in folder", len(images))
    return images


def run_ingestion(settings: Settings, mode: IngestMode) -> str:
    job_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)

    job_store[job_id] = {
        "job_id": job_id,
        "status": IngestStatus.PROCESSING,
        "total": 0,
        "processed": 0,
        "failed": 0,
        "skipped": 0,
        "failed_items": [],
        "started_at": started_at,
        "finished_at": None,
    }

    # Initialize Pinecone connection
    try:
        init_pinecone(settings.pinecone_api_key, settings.pinecone_index_name)
    except Exception as e:
        logger.error("Pinecone initialization failed: %s", e)
        job_store[job_id]["status"] = IngestStatus.FAILED
        job_store[job_id]["failed_items"].append(
            FailedItem(filename="N/A", error=f"Pinecone init failed: {e}")
        )
        job_store[job_id]["finished_at"] = datetime.now(timezone.utc)
        return job_id

    try:
        images = scan_image_folder(settings.image_folder_path)
    except FileNotFoundError as e:
        logger.error("Folder scan failed: %s", e)
        job_store[job_id]["status"] = IngestStatus.FAILED
        job_store[job_id]["failed_items"].append(
            FailedItem(filename="N/A", error=str(e))
        )
        job_store[job_id]["finished_at"] = datetime.now(timezone.utc)
        return job_id

    # Load vendor CSV once before processing images
    csv_lookup = load_csv_lookup(settings.csv_file_path)
    if not csv_lookup:
        logger.warning(
            "job_id=%s CSV lookup empty — all images will use vision-only path", job_id
        )

    job_store[job_id]["total"] = len(images)

    for image_path in images:
        filename = image_path.name
        try:
            file_hash = compute_file_hash(image_path) # compute hash of the image to avoid duplication
            logger.info(
                "job_id=%s Processing %s (hash=%s)", job_id, filename, file_hash[:12]
            )

            # Dedup: skip if hash already exists in Pinecone (incremental mode)
            if mode == IngestMode.INCREMENTAL and hash_exists(file_hash):
                logger.info(
                    "job_id=%s Skipping %s — already ingested (hash=%s)",
                    job_id, filename, file_hash[:12],
                )
                job_store[job_id]["skipped"] += 1
                continue

            # Stage 1: Vision — raw visual analysis from Gemini
            vision_output = extract_metadata(
                api_key=settings.gemini_api_key,
                image_path=image_path,
                model_name=settings.vision_model_name,
            )

            # Stage 2: Merge — combine vision with vendor CSV (CSV corrects factual fields)
            csv_row = get_csv_row(csv_lookup, image_path)
            merged_output = merge_product_data(
                api_key=settings.gemini_api_key,
                model_name=settings.merge_model_name,
                vision_output=vision_output,
                csv_row=csv_row,
            )

            # Inject CSV-only fields directly — gender never comes from the LLM
            merged_output["gender"] = csv_row.get("gender", "") if csv_row else ""
            merged_output["product_display_name"] = csv_row.get("productDisplayName", "") if csv_row else ""
            merged_output["season"] = csv_row.get("season", "") if csv_row else ""

            # Normalize taxonomy fields on the merged output
            metadata = normalize_vision_output(merged_output)

            # Attach pipeline fields
            metadata["raw_vision_output"] = vision_output.get("raw_vision_output", "")
            metadata["model_version"] = vision_output.get("model_version", "")
            metadata["file_hash"] = file_hash
            metadata["image_path"] = filename
            metadata["product_id"] = str(uuid.uuid4())
            metadata["ingested_at"] = datetime.now(timezone.utc).isoformat()

            logger.info(
                "job_id=%s product_id=%s Merged: category=%s colors=%s occasion=%s gender=%s",
                job_id, metadata["product_id"], metadata["category"],
                metadata["colors"], metadata["occasion"], metadata.get("gender", ""),
            )

            # Step 2: Embed — construct text and generate embedding vector
            embedding_text = build_embedding_text(metadata)
            vector = generate_embedding(settings.openai_api_key, embedding_text)

            logger.info(
                "job_id=%s product_id=%s Embedding generated (%d dimensions)",
                job_id, metadata["product_id"], len(vector),
            )

            # Step 3: Store — upsert vector + metadata to Pinecone
            upsert_vector(metadata["product_id"], vector, metadata)

            logger.info(
                "job_id=%s product_id=%s Upserted to Pinecone",
                job_id, metadata["product_id"],
            )

            job_store[job_id]["processed"] += 1

        except (OSError, RuntimeError) as e:
            logger.error("job_id=%s Failed to process %s: %s", job_id, filename, e)
            job_store[job_id]["failed"] += 1
            job_store[job_id]["failed_items"].append(
                FailedItem(filename=filename, error=str(e))
            )

    # Determine final status based on results
    processed = job_store[job_id]["processed"]
    failed = job_store[job_id]["failed"]
    skipped = job_store[job_id]["skipped"]

    if failed > 0 and processed == 0:
        job_store[job_id]["status"] = IngestStatus.FAILED
    else:
        job_store[job_id]["status"] = IngestStatus.COMPLETED

    job_store[job_id]["finished_at"] = datetime.now(timezone.utc)

    logger.info(
        "job_id=%s Ingestion finished. status=%s processed=%d skipped=%d failed=%d",
        job_id,
        job_store[job_id]["status"].value,
        processed,
        skipped,
        failed,
    )
    return job_id


def get_job_status(job_id: str) -> dict | None:
    return job_store.get(job_id)
