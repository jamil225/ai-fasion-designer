from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class HealthResponse(BaseModel):
    status: str
    pinecone: str
    version: str


# --- Ingestion Schemas ---

class IngestMode(str, Enum):
    FULL = "full"
    INCREMENTAL = "incremental"


class IngestRequest(BaseModel):
    mode: IngestMode = IngestMode.FULL


class FailedItem(BaseModel):
    filename: str
    error: str


class IngestStatus(str, Enum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class IngestResponse(BaseModel):
    job_id: str
    queued_count: int
    status: IngestStatus


class IngestStatusResponse(BaseModel):
    job_id: str
    status: IngestStatus
    total: int
    processed: int
    skipped: int = 0
    failed: int
    failed_items: list[FailedItem]
    started_at: datetime
    finished_at: datetime | None = None


# --- Search Schemas ---

class SearchFilters(BaseModel):
    colors: list[str] | None = None
    occasion: str | None = None
    category: list[str] | None = None


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Natural language search query")
    top_k: int = Field(default=10, ge=1, le=100)
    strict_mode: bool = False
    filters: SearchFilters | None = None


class MatchedAttributes(BaseModel):
    colors: list[str]
    occasion: str
    category: str


class SearchResultItem(BaseModel):
    product_id: str
    image_path: str
    score: float
    matched_attributes: MatchedAttributes
    caption: str
    style_tags: list[str]


class SearchResponse(BaseModel):
    results: list[SearchResultItem]
    applied_filters: dict | None = None
    total_results: int
    latency_ms: int


# --- Styled Search Schemas ---

class StyledSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Natural language style query")
    combo_count: int = Field(default=3, ge=1, le=10, description="Max outfit combos to return")
    top_k: int = Field(default=20, ge=5, le=50, description="Vector search breadth")


class StyledProductItem(BaseModel):
    product_id: str
    image_path: str
    category: str
    colors: list[str]
    score: float
    caption: str


class OutfitCombo(BaseModel):
    combo_rank: int
    top: StyledProductItem
    bottom: StyledProductItem
    styling_rationale: str


class StandaloneOutfit(BaseModel):
    product_id: str
    image_path: str
    category: str
    colors: list[str]
    score: float
    caption: str
    rationale: str


class QueryEnrichment(BaseModel):
    original_query: str
    enriched_query: str


class StyledSearchResponse(BaseModel):
    combos: list[OutfitCombo]
    standalone_outfits: list[StandaloneOutfit]
    query_enrichment: QueryEnrichment
    total_results_from_vector: int
    latency_ms: int
