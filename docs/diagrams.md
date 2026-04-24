# AI Fashion Designer — Architecture Diagrams

> **How to render:** Copy each Mermaid block into [mermaid.live](https://mermaid.live/edit) for instant PNG/SVG export.
> Also renders natively on GitHub and in VS Code (with Mermaid extension).

---

## 1. Functional Use Case — "How It Works" (Start Here)

This is the 30-second overview for anyone new to the system.

```mermaid
flowchart LR
    subgraph ONE["**1. INGEST**"]
        direction TB
        IMG["Fashion Images<br/>+ Vendor CSV"]
        AI1["Gemini Vision<br/>extracts metadata"]
        VEC["OpenAI creates<br/>vector embedding"]
        DB[("Pinecone<br/>Vector DB")]
        IMG --> AI1 --> VEC --> DB
    end

    subgraph TWO["**2. SEARCH**"]
        direction TB
        USR["User types:<br/><i>'Golden wedding look'</i>"]
        AGT1["Vector Search Agent<br/><small>Gemini Flash</small><br/>enriches query"]
        PC[("Pinecone<br/>finds similar items")]
        AGT2["Stylist Agent<br/><small>Gemini Pro</small><br/>pairs outfits"]
        OUT["Matched Outfit Combos<br/><small>Top + Bottom + Rationale</small>"]
        USR --> AGT1 --> PC --> AGT2 --> OUT
    end

    ONE ~~~ TWO

    style ONE fill:#f0f7ff,stroke:#0071e3,stroke-width:2px
    style TWO fill:#fff7f0,stroke:#e36500,stroke-width:2px
    style DB fill:#e8f5e9,stroke:#2e7d32
    style PC fill:#e8f5e9,stroke:#2e7d32
    style AGT1 fill:#fff3e0,stroke:#e65100
    style AGT2 fill:#fce4ec,stroke:#c62828
    style AI1 fill:#fff3e0,stroke:#e65100
```

---

## 2. High-Level Design (HLD)

System-level view showing external services, data flow, and component boundaries.

```mermaid
flowchart TB
    subgraph CLIENT["Client Layer"]
        UI["Web UI<br/><small>index.html</small>"]
        SWAGGER["Swagger /docs"]
    end

    subgraph API["FastAPI Application"]
        direction TB
        AUTH["Auth Middleware<br/><small>X-API-Key / Google OAuth</small>"]
        ROUTES["API Routes<br/><small>/v1/health<br/>/v1/ingest/start<br/>/v1/search<br/>/v1/search/styled</small>"]
        AUTH --> ROUTES
    end

    subgraph INGEST_PIPE["Ingestion Pipeline"]
        direction LR
        SCAN["Folder Scanner<br/>+ Dedup"]
        VISION["Vision Extractor<br/><small>Gemini Flash Lite</small>"]
        MERGE["CSV Merger<br/><small>Gemini Flash Lite</small>"]
        TAXO["Taxonomy<br/>Normalizer"]
        EMBED_I["Embedding<br/>Generator"]
        SCAN --> VISION --> MERGE --> TAXO --> EMBED_I
    end

    subgraph SEARCH_PIPE["Styled Search Pipeline"]
        direction LR
        ENRICH["Query Enrichment<br/><small>Gemini Flash</small>"]
        EMBED_S["Embedding<br/>Generator"]
        VECTOR["Vector Search"]
        STYLIST["Stylist Agent<br/><small>Gemini Pro</small>"]
        RESOLVE["Result Resolver<br/>+ Validator"]
        ENRICH --> EMBED_S --> VECTOR --> STYLIST --> RESOLVE
    end

    subgraph EXTERNAL["External Services"]
        GEMINI["Google Gemini API<br/><small>Flash Lite / Flash / Pro</small>"]
        OPENAI["OpenAI API<br/><small>text-embedding-3-small</small>"]
        PINE[("Pinecone<br/><small>fashion-rag index<br/>1536 dimensions<br/>cosine similarity</small>")]
    end

    subgraph DATA["Data Sources"]
        IMAGES["Image Folder<br/><small>jpg, png, webp</small>"]
        CSV["Vendor CSV<br/><small>gender, subCategory<br/>articleType, baseColour</small>"]
        ENV[".env Config<br/><small>API keys, paths</small>"]
    end

    CLIENT --> API
    ROUTES --> INGEST_PIPE
    ROUTES --> SEARCH_PIPE
    INGEST_PIPE --> GEMINI
    INGEST_PIPE --> OPENAI
    INGEST_PIPE --> PINE
    SEARCH_PIPE --> GEMINI
    SEARCH_PIPE --> OPENAI
    SEARCH_PIPE --> PINE
    DATA --> INGEST_PIPE

    style CLIENT fill:#f5f5f7,stroke:#8e8e93
    style API fill:#e3f2fd,stroke:#1565c0,stroke-width:2px
    style INGEST_PIPE fill:#f0f7ff,stroke:#0071e3
    style SEARCH_PIPE fill:#fff7f0,stroke:#e36500
    style EXTERNAL fill:#f3e5f5,stroke:#7b1fa2
    style PINE fill:#e8f5e9,stroke:#2e7d32
    style DATA fill:#fff8e1,stroke:#f9a825
```

---

## 3. Low-Level Design (LLD)

Module-level view showing every file, function, and data model.

```mermaid
flowchart TB
    subgraph MAIN["main.py"]
        R1["GET /v1/health"]
        R2["POST /v1/ingest/start"]
        R3["POST /v1/search"]
        R4["POST /v1/search/styled"]
        R5["GET /v1/images"]
        R6["DELETE /v1/pinecone/clear"]
    end

    subgraph CONFIG["config.py"]
        SETTINGS["Settings<br/><small>gemini_api_key<br/>vision_model_name: flash-lite<br/>merge_model_name: flash-lite<br/>search_enrichment_model_name: flash<br/>stylist_model_name: pro<br/>openai_api_key<br/>pinecone_api_key<br/>best_match_score_threshold</small>"]
    end

    subgraph SCHEMAS["schemas.py"]
        direction LR
        S_IN["IngestRequest<br/>IngestResponse<br/>IngestStatusResponse"]
        S_SEARCH["SearchRequest<br/>SearchResponse<br/>SearchResultItem"]
        S_STYLED["StyledSearchRequest<br/>StyledSearchResponse<br/>OutfitCombo<br/>StandaloneOutfit<br/>StyledProductItem<br/>QueryEnrichment"]
    end

    subgraph INGESTION["ingestion.py"]
        RUN_ING["run_ingestion()<br/><small>scan_image_folder()<br/>compute_file_hash()<br/>job_store dict</small>"]
    end

    subgraph VISION_MOD["vision.py"]
        EXTRACT["extract_metadata()<br/><small>VISION_PROMPT<br/>category, wear_type, colors<br/>occasion, style_tags, caption<br/>pattern, fabric_hint</small>"]
    end

    subgraph MERGE_MOD["merge.py"]
        MERGE_FN["merge_product_data()<br/><small>CSV corrects factual fields<br/>Vision provides descriptive<br/>Passes through vision_wear_type</small>"]
    end

    subgraph TAXONOMY["taxonomy.py"]
        NORM["normalize_vision_output()<br/><small>normalize_color()<br/>normalize_category()<br/>normalize_occasion()<br/>normalize_wear_type()<br/><br/>WEAR_TYPE_MAP<br/>COLOR_SYNONYMS<br/>CATEGORY_SYNONYMS</small>"]
    end

    subgraph EMBED["embeddings.py"]
        BUILD["build_embedding_text()<br/><small>'{gender} {category}.<br/>in {colors} colors.<br/>for {occasion} occasion.<br/>{style_tags}. {caption}'</small>"]
        GEN["generate_embedding()<br/><small>OpenAI text-embedding-3-small<br/>1536 dimensions</small>"]
    end

    subgraph PINECONE["pinecone_client.py"]
        UPSERT["upsert_vector()<br/><small>16 metadata fields<br/>+ wear_type</small>"]
        QUERY["query_vectors()<br/><small>cosine similarity<br/>returns 12 fields</small>"]
        HASH["hash_exists()<br/><small>dedup check</small>"]
    end

    subgraph QE["query_enrichment.py"]
        ENRICH_FN["enrich_query()<br/><small>Gemini Flash<br/>Expands user query<br/>max 100 words<br/>Aligned to embedding format</small>"]
    end

    subgraph STYLIST["stylist_agent.py"]
        CURATE["curate_outfits()<br/><small>Gemini Pro<br/>5 pairing rules:<br/>gender, color harmony<br/>occasion, season, style<br/>Returns product_ids + rationale</small>"]
    end

    subgraph ORCH["styled_search.py"]
        RUN_SS["run_styled_search()<br/><small>1. enrich_query<br/>2. generate_embedding<br/>3. query_vectors<br/>4. score threshold<br/>5. curate_outfits<br/>6. validate + resolve IDs</small>"]
    end

    subgraph CSV_MOD["csv_loader.py"]
        LOAD["load_csv_lookup()<br/>get_csv_row()"]
    end

    R2 --> RUN_ING
    R3 --> S_SEARCH
    R4 --> RUN_SS
    RUN_ING --> EXTRACT
    RUN_ING --> MERGE_FN
    RUN_ING --> NORM
    RUN_ING --> BUILD
    RUN_ING --> GEN
    RUN_ING --> UPSERT
    RUN_ING --> HASH
    RUN_ING --> LOAD
    RUN_SS --> ENRICH_FN
    RUN_SS --> GEN
    RUN_SS --> QUERY
    RUN_SS --> CURATE
    MERGE_FN --> LOAD

    style MAIN fill:#e3f2fd,stroke:#1565c0,stroke-width:2px
    style CONFIG fill:#fff8e1,stroke:#f9a825
    style SCHEMAS fill:#f3e5f5,stroke:#7b1fa2
    style INGESTION fill:#f0f7ff,stroke:#0071e3
    style ORCH fill:#fff7f0,stroke:#e36500
    style QE fill:#fff3e0,stroke:#e65100
    style STYLIST fill:#fce4ec,stroke:#c62828
    style PINECONE fill:#e8f5e9,stroke:#2e7d32
```

---

## 4. Sequence Diagram — Styled Search Flow

End-to-end request lifecycle for `POST /v1/search/styled`.

```mermaid
sequenceDiagram
    actor User
    participant UI as Web UI
    participant API as FastAPI
    participant QE as Query Enrichment<br/>(Gemini Flash)
    participant OAI as OpenAI<br/>Embeddings
    participant PC as Pinecone
    participant SA as Stylist Agent<br/>(Gemini Pro)

    User->>UI: "Golden wedding look"
    UI->>API: POST /v1/search/styled<br/>{"query": "Golden wedding look", "combo_count": 3}
    API->>API: verify_auth (X-API-Key)

    rect rgb(255, 247, 240)
        Note over API,SA: Styled Search Pipeline (styled_search.py)

        API->>QE: enrich_query("Golden wedding look")
        QE-->>API: "elegant gold festive wedding formal<br/>kurta blazer trousers lehenga saree<br/>silk embroidered traditional..."

        API->>OAI: generate_embedding(enriched_query)
        OAI-->>API: float[1536]

        API->>PC: query_vectors(vector, top_k=20)
        PC-->>API: 20 results with metadata<br/>(product_id, category, colors,<br/>wear_type, gender, score...)

        API->>API: Filter by score threshold (0.20)<br/>15 results remain

        API->>SA: curate_outfits(<br/>original_query,<br/>15 products,<br/>combo_count=3)

        Note over SA: Applies 5 pairing rules:<br/>1. Gender consistency<br/>2. Color harmony<br/>3. Occasion coherence<br/>4. Season alignment<br/>5. Style coherence

        SA-->>API: {combos: [{top_id, bottom_id,<br/>rationale}...],<br/>standalone_outfits: [...]}

        API->>API: Validate product_ids<br/>Prevent duplicates<br/>Resolve to full metadata
    end

    API-->>UI: StyledSearchResponse<br/>{combos, standalone_outfits,<br/>query_enrichment, latency_ms}

    UI->>UI: Render combo cards<br/>[Top Image] + [Bottom Image]<br/>+ Styling Rationale

    UI-->>User: Outfit combinations displayed
```

---

## 5. Sequence Diagram — Ingestion Pipeline

End-to-end flow for `POST /v1/ingest/start` (per image).

```mermaid
sequenceDiagram
    actor Admin
    participant API as FastAPI
    participant ING as Ingestion<br/>Pipeline
    participant FS as File System
    participant CSV as CSV Loader
    participant GV as Gemini Vision<br/>(Flash Lite)
    participant GM as Gemini Merge<br/>(Flash Lite)
    participant TAX as Taxonomy<br/>Normalizer
    participant OAI as OpenAI<br/>Embeddings
    participant PC as Pinecone

    Admin->>API: POST /v1/ingest/start<br/>{"mode": "full"}
    API->>ING: run_ingestion(settings, mode)

    ING->>PC: init_pinecone()
    ING->>FS: scan_image_folder()
    FS-->>ING: [image1.jpg, image2.jpg, ...]
    ING->>CSV: load_csv_lookup(csv_path)
    CSV-->>ING: {image_id: {gender, subCategory, ...}}

    loop For each image
        ING->>ING: compute_file_hash(SHA-256)

        opt Incremental mode
            ING->>PC: hash_exists(file_hash)?
            PC-->>ING: true/false
            Note over ING: Skip if already ingested
        end

        rect rgb(240, 247, 255)
            Note over ING,PC: Processing Pipeline

            ING->>GV: extract_metadata(image)
            GV-->>ING: {category, wear_type, colors,<br/>occasion, style_tags, caption,<br/>pattern, fabric_hint}

            ING->>CSV: get_csv_row(image_id)
            CSV-->>ING: {gender, subCategory,<br/>articleType, baseColour, ...}

            ING->>GM: merge_product_data(vision, csv)
            Note over GM: CSV corrects factual fields<br/>Vision provides descriptive fields
            GM-->>ING: merged metadata<br/>+ vision_wear_type

            ING->>TAX: normalize_vision_output(merged)
            TAX-->>ING: normalized metadata

            ING->>TAX: normalize_wear_type(<br/>csv.subCategory,<br/>vision_wear_type,<br/>category)
            Note over TAX: Tier 1: CSV subCategory<br/>Tier 2: Vision LLM<br/>Tier 3: Category mapping
            TAX-->>ING: "topwear" | "bottomwear" | "full_body"

            ING->>OAI: generate_embedding(text)
            OAI-->>ING: float[1536]

            ING->>PC: upsert_vector(id, vector,<br/>metadata + wear_type)
        end
    end

    ING-->>API: job_id (completed)
    API-->>Admin: {job_id, status, processed, failed}
```

---

## Quick Reference — File Map

```
src/
 main.py                 API routes + app setup
 config.py               Settings (Pydantic, .env, application.toml)
 schemas.py              All request/response Pydantic models
 auth.py                 X-API-Key + Google OAuth middleware
 ingestion.py            Ingestion orchestrator (sequential, per-image)
 vision.py               Gemini Vision metadata extraction
 merge.py                CSV + Vision merge via Gemini LLM
 csv_loader.py           Vendor CSV loading + lookup
 taxonomy.py             Canonical values + synonym maps + wear_type
 embeddings.py           Embedding text construction + OpenAI API
 pinecone_client.py      Pinecone init/upsert/query/dedup
 search.py               Standard vector search (soft/strict modes)
 query_enrichment.py     Vector Search Agent (Gemini Flash)
 stylist_agent.py        Stylist Agent (Gemini Pro)
 styled_search.py        Two-agent pipeline orchestrator
 static/index.html       Web UI (standard + styled search)
```
