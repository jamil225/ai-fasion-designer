# AI Fashion Designer — Architecture & System Diagrams (v3.2)

Executive architectural specification and system diagrams for the **AI Fashion Designer RAG Platform (v3.2)**. 

---

## Architecture Evolution Overview

| Architectural Dimension | v1 Baseline (Phase I RAG) | v3.2 Current Production Architecture |
|---|---|---|
| **Execution Pattern** | Linear 2-agent sequential pipeline (`enrich` → `vector` → `curate`) | **LangGraph ReAct Agent State Machine** (`FashionAgentState` with operator reducers) |
| **User Interaction** | Single-turn stateless request/response | **Multi-turn stateful conversational chat** with Human-In-The-Loop (HITL) slot gathering |
| **LLM Connectivity** | Direct SDK calls per module; single provider | **Modular LLM Gateway** (`src/llm_gateway/`) with Vertex AI primary + OpenAI failover |
| **Guardrails & Safety** | None | **Strategy Pattern Guardrail Registry** (`config/guardrails.yaml` + OpenAI Moderation) |
| **Observability** | Console logging | **LangSmith Tracing** with `@traceable` child spans (`retriever` & `chain` runs) |
| **Deployment & Ops** | Local manual script | **GCP VM** (`e2-small`), Nginx SSL proxy (`nip.io`), Systemd, 1-touch deploy (`deploy-and-open.sh`) |

---

## 1. Functional Architecture (v2)

High-level operational topology illustrating ingestion and agentic execution.

```mermaid
flowchart LR
    subgraph INGEST["**1. MULTIMODAL INGESTION PIPELINE**"]
        direction TB
        IMG["Garment Images<br/>+ Vendor CSV"]
        VIS["Gemini Vision<br/>(Vertex AI ADC)<br/>Extracts Metadata"]
        NORM["Taxonomy Engine<br/>Normalizes Enums"]
        EMB["OpenAI Embeddings<br/>text-embedding-3-small"]
        PINE[("Pinecone Vector DB<br/>1536d Cosine Index")]
        LOG["Ingestion CSV Log<br/>ingestion_log.csv"]

        IMG --> VIS --> NORM --> EMB --> PINE
        PINE --> LOG
    end

    subgraph AGENT["**2. LANGGRAPH AGENTIC STYLIST PIPELINE**"]
        direction TB
        USR["User Chat Prompt<br/><i>'Casual suit for men'</i>"]
        GUARD["Guardrail Layer<br/>OpenAI Moderation API"]
        GRAPH["LangGraph ReAct Agent<br/>FashionAgentState"]
        GATEWAY["LLM Gateway<br/>Vertex AI (Primary)<br/>OpenAI Failover"]
        TOOLS["Agent Tools<br/>• check_required_fields<br/>• ask_user (HITL Slot Clarification)<br/>• enrich_query<br/>• search_products (Pinecone)<br/>• curate_outfits (InjectedState)"]
        OUT["Curated Outfit Combos<br/>+ Rationales + Cart Actions"]

        USR --> GUARD --> GRAPH
        GRAPH <--> GATEWAY
        GRAPH <--> TOOLS
        GRAPH --> OUT
    end

    INGEST ~~~ AGENT

    style INGEST fill:#f0f7ff,stroke:#0071e3,stroke-width:2px
    style AGENT fill:#fff7f0,stroke:#e36500,stroke-width:2px
    style PINE fill:#e8f5e9,stroke:#2e7d32
    style GATEWAY fill:#f3e5f5,stroke:#7b1fa2
    style GRAPH fill:#fff3e0,stroke:#e65100
    style GUARD fill:#ffebee,stroke:#c62828
```

---

## 2. High-Level Design — HLD (v2)

System-level boundaries, infrastructure deployment, and provider interfaces.

```mermaid
flowchart TB
    subgraph CLIENT["Client Layer"]
        UI["React 19 Luxury UI<br/><small>Vite / Port 5173</small>"]
        SWAGGER["Swagger UI<br/><small>/docs / Port 8083</small>"]
    end

    subgraph INFRA["GCP Compute Engine Infrastructure"]
        direction TB
        NGINX["Nginx Reverse Proxy<br/><small>Let's Encrypt SSL (8.234.93.21.nip.io)</small>"]
        SYSTEMD["Systemd Unit<br/><small>ai-fashion-backend.service</small>"]
        NGINX -->|Proxy /v1/* -> 127.0.0.1:8083| SYSTEMD
    end

    subgraph APP["FastAPI Application (Port 8083)"]
        direction TB
        AUTH["Auth Middleware<br/><small>X-API-Key / Google OAuth JWT</small>"]
        GUARD_MGR["Guardrail Registry<br/><small>OpenAI Moderation / config/guardrails.yaml</small>"]
        ROUTES["API Routes<br/><small>/v1/chat, /v1/search/styled, /v1/ingest/start</small>"]
        AUTH --> GUARD_MGR --> ROUTES
    end

    subgraph AGENT_ENGINE["LangGraph ReAct Agent Subsystem"]
        direction TB
        GRAPH["Agent Graph (graph.py)<br/><small>create_react_agent / FashionAgentState</small>"]
        TOOLS["State-Writing Tools (tools.py)<br/><small>check_required_fields | ask_user (HITL)<br/>enrich_query | search_products | curate_outfits</small>"]
        PROMPTS["YAML Prompt Loader<br/><small>prompts/agent_prompts.yaml</small>"]
        GRAPH <--> TOOLS
        GRAPH <--> PROMPTS
    end

    subgraph LLM_GATEWAY["LLM Gateway (src/llm_gateway/)"]
        direction TB
        FACADE["Gateway Façade (gateway.py)"]
        ROUTER["LiteLLM Router<br/><small>Text Failover & Cost Tracking</small>"]
        FALLBACK["LangChain with_fallbacks<br/><small>Agent Chat Failover</small>"]
        FACADE --> ROUTER
        FACADE --> FALLBACK
    end

    subgraph EXTERNAL["External AI & Database Providers"]
        VERTEX["Google Vertex AI<br/><small>Gemini 2.5 Pro (ADC)</small>"]
        OPENAI["OpenAI API<br/><small>text-embedding-3-small<br/>gpt-5.6-terra Failover</small>"]
        PINE[("Pinecone Vector DB<br/><small>fashion-rag index</small>")]
        LANGSMITH["LangSmith Observability<br/><small>Child Spans & Tracing</small>"]
    end

    CLIENT --> NGINX
    SYSTEMD --> APP
    ROUTES --> AGENT_ENGINE
    AGENT_ENGINE --> LLM_GATEWAY
    LLM_GATEWAY --> VERTEX
    LLM_GATEWAY --> OPENAI
    TOOLS --> PINE
    APP --> LANGSMITH

    style CLIENT fill:#f5f5f7,stroke:#8e8e93
    style INFRA fill:#e8eaf6,stroke:#283593,stroke-width:2px
    style APP fill:#e3f2fd,stroke:#1565c0,stroke-width:2px
    style AGENT_ENGINE fill:#fff7f0,stroke:#e36500,stroke-width:2px
    style LLM_GATEWAY fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    style EXTERNAL fill:#e8f5e9,stroke:#2e7d32
```

### Component Responsibility Specification

- **Infrastructure Host**: Single GCE `e2-small` instance in `asia-south1-a` (Mumbai). Systemd manages `ai-fashion-backend.service` on `127.0.0.1:8083`; Nginx terminates Let's Encrypt SSL and proxies traffic.
- **LLM Gateway Façade**: Decouples business logic from providers. Text calls use LiteLLM `Router` (cooldown + failover); agent chat uses LangChain `with_fallbacks` (Vertex AI primary → OpenAI `gpt-5.6-terra` Responses API failover).
- **Guardrails System**: Pre-execution input validation via `OpenAI Moderation API`. YAML kill-switch (`config/guardrails.yaml`) provides zero-latency dev bypass.

---

## 3. Low-Level Design — LLD (v2)

Module-level design detailing component composition, state reducers, and tools.

```mermaid
flowchart TB
    subgraph AGENT_MOD["src/agent/"]
        ROUTES["routes.py<br/><small>POST /v1/chat<br/>Thread state & HITL resume</small>"]
        GRAPH["graph.py<br/><small>create_react_agent()<br/>FashionAgentState</small>"]
        TOOLS["tools.py<br/><small>check_required_fields()<br/>ask_user()<br/>enrich_query()<br/>search_products()<br/>curate_outfits()</small>"]
        SCHEMAS_A["schemas.py<br/><small>FashionAgentState<br/>SlotCheckResult<br/>SearchFilters<br/>Product, OutfitCombo</small>"]
        PROMPT_L["prompt_loader.py<br/><small>load_prompt() @lru_cache</small>"]
        GUARD_DIR["guardrails/<br/><small>registry.py<br/>openai_moderation.py</small>"]
    end

    subgraph GATEWAY_MOD["src/llm_gateway/"]
        GW["gateway.py<br/><small>LLMGateway façade<br/>generate_text()<br/>get_chat_model()</small>"]
        PROV["providers.py<br/><small>build_text_router()<br/>build_chat_model()</small>"]
        CB["callbacks.py<br/><small>LiteLLM & LangSmith hooks</small>"]
    end

    subgraph CORE_MOD["src/ (Core System)"]
        MAIN["main.py<br/><small>FastAPI application<br/>LangSmith init & router mount</small>"]
        CONFIG["config.py<br/><small>Settings (pydantic-settings)<br/>Vertex / OpenAI / Pinecone knobs</small>"]
        INGEST["ingestion.py<br/><small>run_ingestion() sequential pipeline</small>"]
        ING_LOG["ingestion_log.py<br/><small>append_ingestion_log_row() CSV</small>"]
        VISION["vision.py<br/><small>extract_metadata() Gemini Vision</small>"]
        MERGE["merge.py<br/><small>merge_product_data() CSV+Vision</small>"]
        TAXO["taxonomy.py<br/><small>normalize_vision_output() Enums</small>"]
        EMBED["embeddings.py<br/><small>generate_embedding() OpenAI</small>"]
        PINE_C["pinecone_client.py<br/><small>upsert_vector() & query_vectors()</small>"]
    end

    subgraph SCRIPTS["scripts/"]
        DEPLOY_S["deploy-and-open.sh<br/><small>macOS one-touch deploy</small>"]
        VM_UPD["vm-update.sh<br/><small>GCP remote build & uvicorn loop</small>"]
        HQ_DL["download_hq_images.py<br/><small>Kaggle batch image downloader</small>"]
    end

    MAIN --> ROUTES
    ROUTES --> GRAPH
    GRAPH --> TOOLS
    GRAPH --> PROMPT_L
    TOOLS --> GW
    GW --> PROV
    PROV --> CB
    TOOLS --> EMBED
    TOOLS --> PINE_C
    INGEST --> VISION
    INGEST --> MERGE
    INGEST --> TAXO
    INGEST --> EMBED
    INGEST --> PINE_C
    INGEST --> ING_LOG

    style AGENT_MOD fill:#fff7f0,stroke:#e36500,stroke-width:2px
    style GATEWAY_MOD fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    style CORE_MOD fill:#e3f2fd,stroke:#1565c0,stroke-width:2px
    style SCRIPTS fill:#e8eaf6,stroke:#283593
```

### Agent Tool Contracts & State Reducers

| Tool Name | Input Parameters | State Operations / Reducer | Purpose |
|---|---|---|---|
| `check_required_fields` | *InjectedState* | None | Validates `gathered_slots` against required search criteria (`gender`, `occasion`). |
| `ask_user` | `question: str` | `Interrupt` exception | Pauses execution via Human-In-The-Loop middleware; returns user response upon resume. |
| `enrich_query` | `query: str` | `gathered_slots` (dict-merge) | Extracts implicit filters and expands semantic search terms via LLM Gateway. |
| `search_products` | `query: str`, `filters: dict` | `last_products` (overwrite), `tool_trace` (`operator.add`) | Queries Pinecone with 5-result cap; emits `@traceable` retriever span. |
| `curate_outfits` | *InjectedState* | `tool_trace` (`operator.add`) | Reads ground-truth `last_products` from state; synthesizes outfit combos + rationales. |

---

## 4. Sequence Diagrams (v2)

### 4.1 Conversational Agent Lifecycle (`POST /v1/chat`)

```mermaid
sequenceDiagram
    actor User
    participant UI as React Luxury UI
    participant API as FastAPI (routes.py)
    participant Guard as Guardrail Registry
    participant Agent as LangGraph ReAct Agent
    participant Gateway as LLM Gateway
    participant PC as Pinecone Vector DB

    User->>UI: Types chat prompt: "Casual suit for men"
    UI->>API: POST /v1/chat {message, thread_id}
    API->>API: Verify Auth (X-API-Key / OAuth)
    API->>Guard: validate_input(message)
    Guard-->>API: Pass (No toxicity/off-topic)

    API->>Agent: AGENT.invoke({"messages": [user_msg]}, config)

    rect rgb(255, 243, 224)
        Note over Agent,Gateway: Turn 1: Slot Gathering & ReAct Loop
        Agent->>Agent: Tool: check_required_fields()
        Note over Agent: State check: gender & occasion present?
        
        alt Missing Required Slots
            Agent->>Agent: Tool: ask_user(consolidated_question)
            Agent-->>API: Interrupt Raised (ask_user)
            API-->>UI: HTTP 200 {status: "interrupted", question: "What occasion/gender?"}
            User->>UI: Selects/types missing slots
            UI->>API: POST /v1/chat {resume_value, thread_id}
            API->>Agent: AGENT.invoke(Command(resume=resume_value), config)
        end
    end

    rect rgb(240, 247, 255)
        Note over Agent,PC: Turn 2: Query Enrichment, Search & Outfit Curation
        Agent->>Agent: Tool: enrich_query("casual suit for men")
        Agent->>Gateway: generate_text(query_enrichment_prompt)
        Gateway-->>Agent: Enriched search terms & filter JSON

        Agent->>Agent: Tool: search_products(query, filters, top_k=5)
        Agent->>PC: query_vectors(embedding, filters, top_k=5)
        PC-->>Agent: 5 matching garment vectors + metadata
        Note over Agent: Write last_products to FashionAgentState

        Agent->>Agent: Tool: curate_outfits() [reads last_products via InjectedState]
        Agent->>Gateway: get_chat_model() (Vertex AI primary → OpenAI failover)
        Gateway-->>Agent: Curated OutfitCombos + Rationales
    end

    Agent-->>API: Final State Output
    API-->>UI: HTTP 200 {messages, products, combos, rationales}
    UI-->>User: Renders Outfit Canvas + Lightbox + Add-to-Cart
```

### 4.2 Garment Ingestion & Metadata Pipeline (`POST /v1/ingest/start`)

```mermaid
sequenceDiagram
    actor Admin
    participant API as FastAPI /v1/ingest/start
    participant Ingest as ingestion.py
    participant Vision as vision.py (Vertex AI)
    participant Merge as merge.py
    participant Taxo as taxonomy.py
    participant Embed as embeddings.py (OpenAI)
    participant PC as Pinecone Client
    participant Log as ingestion_log.py

    Admin->>API: POST /v1/ingest/start
    API->>Ingest: run_ingestion() [Synchronous Sequential]
    
    loop For each image in IMAGE_FOLDER_PATH
        Ingest->>Ingest: Compute SHA-256 file hash
        Ingest->>PC: hash_exists(file_hash)
        
        alt Vector Already Exists (Dedup Hit)
            PC-->>Ingest: True
            Note over Ingest: Skip duplicate image
        else New Image (Dedup Miss)
            PC-->>Ingest: False
            Ingest->>Vision: extract_metadata(image_bytes)
            Vision-->>Ingest: Vision JSON (category, wear_type, color, occasion, style_tags)
            
            Ingest->>Merge: merge_product_data(vision_json, csv_lookup)
            Merge-->>Ingest: Merged Metadata Dict
            
            Ingest->>Taxo: normalize_vision_output(merged_dict)
            Taxo-->>Ingest: Taxonomy Normalized Enums
            
            Ingest->>Embed: generate_embedding(composite_text)
            Embed-->>Ingest: float[1536] Vector
            
            Ingest->>PC: upsert_vector(id=hash, vector, metadata)
            PC-->>Ingest: Success
            
            Ingest->>Log: append_ingestion_log_row(hash, filename, metadata)
            Log-->>Ingest: CSV Row Appended
        end
    end
    
    Ingest-->>API: IngestStatusResponse {total, processed, skipped, failed}
    API-->>Admin: HTTP 200 Ingestion Summary
```

---

## 5. Historical Baseline Diagrams (v1)

For reference, original Phase 1 baseline diagrams are preserved under:
- **Functional Use Case (v1)**: `docs/images/v1/01-functional-usecase.png` | `docs/mmd/v1/01-functional-usecase.mmd`
- **High-Level Design (v1)**: `docs/images/v1/02-hld.png` | `docs/mmd/v1/02-hld.mmd`
- **Low-Level Design (v1)**: `docs/images/v1/03-lld.png` | `docs/mmd/v1/03-lld.mmd`
