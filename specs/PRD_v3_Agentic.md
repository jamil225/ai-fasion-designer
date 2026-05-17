# PRD v3.0 — Agentic Edition: Single-Agent ReAct for AI Fashion Designer

## Brief Summary

Re-baseline the AI Fashion Designer from a hand-orchestrated LLM pipeline (frozen on the `llm-implementation` branch) to a **production-grade single-agent ReAct system** built on LangGraph. The agent uses Gemini 2.5 Flash with five typed tools (`check_required_fields`, `ask_user`, `enrich_query`, `search_products`, `curate_outfits`), pauses for required user input via LangGraph's HITL middleware, persists per-conversation state via a structured `FashionAgentState` checkpointed by `thread_id`, and supports **multi-turn variant refinement** ("add red", "make it more formal") within a hard cap of 5 results per search. A new `/v1/chat` endpoint surfaces the agentic experience; existing `/v1/search` and `/v1/styled-search` endpoints stay as-is.

v3.0 ships the **agent core plus multi-turn refinement and YAML-externalized prompts**. Full observability (LangSmith), guardrails (Guardrails-AI / NeMo), eval harness, conversation summarization, and deployment (Docker / cloud) defer to **v3.1+**, each as its own incremental PRD.

This PRD supersedes `PRD_v2_Phase1_Vision_First_RAG.md` for everything related to the chat surface. The vision-first RAG ingestion and search internals from PRD v2 carry forward unchanged and are wrapped as tools in v3.0 via the parallel-wrapper pattern (DEC-016) — original modules stay byte-for-byte intact so the legacy endpoints keep working.

---

## Development Philosophy

> **Build the smallest agentic surface that is still genuinely agentic, and make every choice defensible against a recruiter or interviewer.**

- Single source of truth for v3.0 = this PRD.
- Every architectural choice cites either official docs (LangChain / LangGraph / LangSmith via the documentation MCP at `https://docs.langchain.com/mcp`) or `learnings/design-decisions-log.md`. No black-box magic.
- Existing pipeline code (`src/query_enrichment.py`, `src/search.py`, `src/stylist_agent.py`) is **reused as tools** with thin wrappers. No rewrite.
- Each milestone (v3.0, v3.1, …) ships independently. v3.0 is end-to-end demoable on its own.
- "Looks impressive" is not a justification. Multi-agent supervisor would look impressive but is **explicitly rejected** for v3.0 per official LangChain guidance (see DEC-010 in `learnings/design-decisions-log.md`).

---

## Goals (v3.0)

- **Genuinely agentic UX**: a conversational `/v1/chat` endpoint where the agent gathers required slots (configurable; v3.0 = gender + occasion), then enriches, searches, and curates outfit combos with mandatory rationale per combo.
- **Multi-turn variant refinement**: within the same `thread_id`, users can refine the result by attribute change ("add red", "make it more formal", "show traditional only"). Pagination requests ("more options", "next page") are **explicitly refused** in v3.0 — max **5 combos** per search.
- **Idiomatic LangGraph**: built on `create_agent` + `HumanInTheLoopMiddleware` + checkpointer + a custom `FashionAgentState` extending `AgentState` — the official patterns from the LangChain OSS Python docs.
- **YAML-externalized prompts**: all prompts (agent system prompt, ask_user phrasing, canned messages, tool-internal prompts) live in `prompts/*.yaml`. No prompts in Python code.
- **Reuse, don't rewrite**: 100% of existing search / enrich / stylist logic stays in place via the parallel-wrapper pattern (DEC-016). Original modules untouched; legacy endpoints unaffected.
- **Recruiter-readable**: a GitHub visitor can read this PRD, then read `src/agent/` and `learnings/design-decisions-log.md`, and understand every choice.
- **Foundation for v3.1+**: the graph and state model extend cleanly to LangSmith, guardrails, evals, and conversation summarization without rewrite.

## Non-Goals (v3.0 — explicit deferrals)

| Deferred to | Item | Why deferred |
|---|---|---|
| v3.1 | LangSmith tracing setup, structured JSON logging via `structlog`, per-node latency metrics | Agent core has to exist first; obs layer is orthogonal. v3.0 emits structured-ish logs via Python `logging` and the `tool_trace` state field. |
| v3.1 | Pagination / "more options" / "show more" — currently REFUSED at the agent layer | Hard cap of 5 results per search; expanding requires UX work (paging UI) + product decisions. |
| v3.1 | Combo-swap refinement ("swap top of combo 2") | Variant refinement covers the most useful demos; combo surgery is finer-grained and lower-priority. |
| v3.1 | Guardrails-AI / NeMo input + output rails | v3.0 ships with Pydantic schema validation + 500-char input cap. |
| v3.1 | Eval harness (LangSmith datasets, golden conversations, regression suite) | Need a working agent to evaluate first. |
| v3.1 | Per-user rate limiting (`slowapi`), daily token budget | Single-tenant prototype in v3.0. |
| v3.1 | Streaming responses via SSE | v3.0 returns JSON; streaming adds frontend complexity. |
| v3.1 | `SummarizationMiddleware` for long conversations | v3.0 uses vanilla history + 20-turn hard cap. Summarization is the proper fix when 20 turns isn't enough. |
| v3.2 | Docker, deployment to cloud (Railway / Cloud Run / Vercel), CI/CD | Build → harden → ship. |
| v3.x | Multi-agent supervisor migration | YAGNI per DEC-010; revisit if v3.x grows beyond ~6 tools or domains cluster. |
| Out of scope | Replace existing `/v1/search` / `/v1/styled-search` | Additive endpoint strategy (DEC-007). |
| Out of scope | Remove static HTML at `src/static/` | Declared deprecated here; cleanup is a v3.1 task. |

---

## Users

| User | Actions in v3.0 |
|---|---|
| End shopper | Opens chat panel in `frontend/`, types a fashion query, answers up to two clarifying questions if asked, receives 2–3 outfit combos each with a rationale |
| Admin / operator | Triggers ingestion (unchanged from PRD v2), monitors job status, can also exercise `/v1/chat` via Swagger |
| Recruiter / interviewer | Reads this PRD + `learnings/design-decisions-log.md` + `learnings/project-build-journal.md` to see the engineering reasoning behind every choice |

---

## Tech Stack (v3.0 additions)

| Component | Technology | Purpose |
|---|---|---|
| Agent framework | LangChain `create_agent` (Python) | Single-agent ReAct + tools + middleware |
| Agent runtime | LangGraph | Graph execution, conditional edges, recursion limit |
| State extension | Custom `FashionAgentState` extending `AgentState` | Structured slots, filters, last_products, turn_count, tool_trace |
| Human-in-the-loop | `HumanInTheLoopMiddleware` | Typed `Interrupt` on `ask_user` tool calls, `respond` decision type |
| Checkpointer | `langgraph.checkpoint.memory.InMemorySaver` | Per-thread state persistence (lost on restart) |
| LLM (orchestrator) | Google `gemini-2.5-flash` via `google-genai` | `agent_node` reasoning + tool calls |
| LLM (stylist, unchanged) | Google `gemini-2.5-pro` via `google-genai` | Inside `curate_outfits` wrapper, delegates to `src/stylist_agent.py` |
| Prompt registry | YAML files in `prompts/` + tiny `prompt_loader.py` | All prompts versioned in git, loaded by key at startup |
| Output validation | Pydantic v2 (already in stack) | Every tool input + output is Pydantic-typed |
| Documentation source-of-truth | LangChain docs MCP server (`https://docs.langchain.com/mcp`) | Citations in PRD + decision log + journal |

**Carried forward unchanged from PRD v2:**
- FastAPI + Swagger UI
- Pinecone (cosine similarity, 1536d)
- OpenAI `text-embedding-3-small` (only for embeddings; not for chat)
- Google `gemini-pro-vision` (only for ingestion; not for chat)
- `.env` + `pydantic-settings`
- API key middleware (`X-API-Key`)

---

## Architecture

### End-to-End Flow (one HTTP turn)

```
POST /v1/chat (initial OR resume)
  ↓
load checkpoint from InMemorySaver[thread_id]  → FashionAgentState restored
  ↓
agent_node (Gemini Flash + system prompt + 5 tools)
  ↓ (one of, per ReAct iteration)
  ├─ tool_call: check_required_fields()  → reads state.gathered_slots → returns SlotCheckResult
  ├─ tool_call: ask_user(question)       → HITL Interrupt → return {type:"interrupt", ...} to client
  ├─ tool_call: enrich_query(...)        → wrapper delegates to src/query_enrichment → state.current_filters updated
  ├─ tool_call: search_products(...)     → wrapper delegates to src/search → state.last_products updated (≤5)
  ├─ tool_call: curate_outfits(...)      → wrapper delegates to src/stylist_agent → state.last_combos updated
  └─ final reply (no tool call)          → return {type:"final", message, combos, observability fields}
  ↓
persist FashionAgentState to InMemorySaver[thread_id]
  ↓
HTTP response (final OR interrupt)
```

### LangGraph topology (compile-time)

Two nodes (`agent`, `tools`) + one conditional edge + one loopback edge. This is the `create_agent` output, not a hand-built `StateGraph`. The HITL middleware sits **inside** `tools_node`, intercepting any `ask_user` tool call before execution.

```
ENTRY → agent_node ─── final reply (no tool calls) ───→ END
                    │
                    └── tool_call ──→ tools_node ──→ agent_node (loopback)
                                            │
                                            └── interrupt raised on ask_user
                                                → checkpoint, return to client
```

**Why two nodes only**: official LangChain guidance — *"Use single agent with middleware for most handoffs use cases — it's simpler."* (`oss/python/langchain/multi-agent/handoffs.mdx`). See DEC-010.

### State — `FashionAgentState`

Custom state schema extends `AgentState` per the `state_schema` parameter on `create_agent` (`oss/python/langchain/short-term-memory.mdx` → "Customizing agent memory"):

```python
class ToolTraceEntry(BaseModel):
    tool_name: str
    latency_ms: int
    error: str | None = None

class FashionAgentState(AgentState):
    # AgentState provides: messages, plus middleware bookkeeping
    gathered_slots: dict[str, str] = {}               # e.g. {"gender": "women", "occasion": "wedding"}
    current_filters: SearchFilters | None = None       # last filters used in search
    last_semantic_query: str | None = None             # last enriched query
    last_products: list[Product] = []                  # last search result (≤5)
    last_combos: list[OutfitCombo] = []                # last curation result
    turn_count: int = 0                                # incremented per agent_node entry
    request_id: str | None = None                      # per-request UUID for log correlation
    tool_trace: list[ToolTraceEntry] = []              # in-state observability — replaces LangSmith in v3.0
```

Tools update these fields via `Command(update={...})` returns — see `oss/python/langchain/short-term-memory.mdx` → "Write short-term memory from tools".

### Memory & Sessions

- **Checkpointer**: `InMemorySaver` (in-process Python dict). Honors PRD v2's "Pinecone only — no DB" rule.
- **Key**: `thread_id` passed by the client in every request.
- **Lost on restart**: acceptable in v3.0 (PRD_v2 made the same trade-off for ingestion jobs). v3.x upgrade path: swap `InMemorySaver` → `AsyncPostgresSaver`. Documented in v3.x roadmap.
- **History strategy**: vanilla (full message history kept). `SummarizationMiddleware` deferred to v3.1 — see Non-Goals.

### Safety nets

- `recursion_limit=10` on the compiled graph — hard cap on `agent → tools → agent` cycles per HTTP turn.
- `MAX_ASK_USER = 3` per thread — enforced by the system prompt counting `ask_user` tool calls in history; on the 4th attempt, agent applies defaults and proceeds.
- `MAX_RESULTS = 5` per search — enforced inside `search_products` wrapper (passes `top_k=5` to the underlying function).
- `MAX_TURNS = 20` per thread — when `state.turn_count > 20`, agent's final reply suggests starting a new thread.

---

## Project Structure (additions)

```
ai-fashion-designer/
├── src/
│   ├── ... (existing files BYTE-FOR-BYTE UNCHANGED — DEC-016 parallel-wrapper pattern)
│   │   query_enrichment.py / search.py / stylist_agent.py keep their current
│   │   signatures so legacy /v1/search + /v1/styled-search endpoints keep working.
│   ├── agent/                       ← NEW for v3.0
│   │   ├── __init__.py
│   │   ├── graph.py                 ← create_agent + HumanInTheLoopMiddleware + checkpointer + FashionAgentState wiring
│   │   ├── tools.py                 ← @tool wrappers (check_required_fields, ask_user, enrich_query, search_products, curate_outfits)
│   │   ├── schemas.py               ← FashionAgentState + Pydantic models for tool IO + /v1/chat request/response
│   │   ├── prompt_loader.py         ← tiny YAML reader — loads prompts/*.yaml by key at startup
│   │   └── routes.py                ← FastAPI handlers for /v1/chat (new + resume) and /v1/chat/threads/{id}
├── prompts/                          ← NEW for v3.0
│   ├── agent_prompts.yaml           ← agent_system_prompt, ask_user_phrasing, canned messages
│   └── tool_prompts.yaml            ← stylist_system_prompt, query_enrichment_prompt (moved out of Python)
├── specs/
│   └── PRD_v3_Agentic.md            ← this file
└── frontend/
    └── src/
        ├── ... (existing files unchanged)
        └── chat/                    ← NEW for v3.0
            ├── ChatPanel.jsx        ← side panel embedded in existing search screen
            ├── InterruptCard.jsx    ← dedicated render for pending ask_user
            ├── chatApi.js           ← POST /v1/chat (new + resume), parse {type: "final" | "interrupt"}
            └── chatState.js         ← thread_id, message history, pending interrupt state
```

Rationale: agent code in `src/agent/` is reviewable as a unit. Prompts in `prompts/` are versioned in git as code artifacts. Frontend chat code grouped in `frontend/src/chat/`. The parallel-wrapper pattern (DEC-016) means `src/agent/tools.py` is the ONLY new module that imports from `src/search.py`, `src/stylist_agent.py`, `src/query_enrichment.py` — those modules are otherwise untouched.

---

## Public APIs

### POST `/v1/chat` — new

Two request shapes share one endpoint.

**Shape 1 — start or continue a conversation:**
```json
{
  "thread_id": "uuid-or-client-generated",
  "message": "yellow dress for a wedding"
}
```

**Shape 2 — resume from a `respond` interrupt:**
```json
{
  "thread_id": "same-uuid-as-before",
  "resume": {
    "decisions": [
      { "type": "respond", "message": "women's" }
    ]
  }
}
```

The handler inspects which shape is present, calls `agent.invoke(...)` accordingly (passing `Command(resume=...)` for shape 2), and returns one of two response shapes.

**Response — final reply:**
```json
{
  "type": "final",
  "thread_id": "uuid",
  "request_id": "uuid",
  "turn_count": 2,
  "message": "Here are 3 looks for a women's wedding occasion:",
  "combos": [
    {
      "combo_id": "uuid",
      "combo_rank": 1,
      "items": [ { "product_id": "...", "image_path": "...", "category": "saree" } ],
      "rationale": "This yellow embroidered saree pairs the festive palette you asked for with traditional silhouettes appropriate for an Indian wedding."
    }
  ],
  "applied_slots": { "gender": "women", "occasion": "wedding" },
  "applied_filters": { "colors": ["yellow"], "occasion": "wedding", "category": ["dress","saree"] },
  "latency_ms": 2840,
  "tool_trace": [
    { "tool_name": "check_required_fields", "latency_ms": 2 },
    { "tool_name": "enrich_query", "latency_ms": 620 },
    { "tool_name": "search_products", "latency_ms": 410 },
    { "tool_name": "curate_outfits", "latency_ms": 1750 }
  ]
}
```

**Response — pending interrupt:**
```json
{
  "type": "interrupt",
  "thread_id": "uuid",
  "request_id": "uuid",
  "turn_count": 1,
  "pending_action": {
    "name": "ask_user",
    "arguments": { "question": "To find the best looks for you, could you tell me: (1) is this for women's or men's wear, and (2) what's the occasion — wedding, party, casual, formal, festive, office, or traditional?" }
  },
  "latency_ms": 480
}
```

Note: `pending_action.arguments.question` always asks for ALL missing required fields in ONE consolidated question (see Slot-Filling Behavior). Frontend renders this as a single InterruptCard; the user answers once and the client sends `Command(resume={decisions:[{type:"respond", message:"..."}]})`.

**Errors:**
- `400` — both `message` and `resume` present, or neither.
- `404` — `thread_id` references a thread that doesn't exist (only relevant for shape 2 resume; shape 1 auto-creates).
- `401` — missing or invalid `X-API-Key`.
- `500` — agent execution failed after `recursion_limit`; client should retry with a fresh `thread_id`.

### GET `/v1/chat/threads/{thread_id}` — new

Diagnostic endpoint to inspect a thread's current state. Returns the message history + any pending interrupt. Useful for debugging during Swagger testing.

**Response (200):**
```json
{
  "thread_id": "uuid",
  "messages": [ { "role": "user", "content": "..." }, { "role": "assistant", "content": "..." } ],
  "pending_action": null,
  "created_at": "2026-05-17T10:00:00Z",
  "last_activity_at": "2026-05-17T10:00:42Z"
}
```

Auth-gated like the rest.

### Existing endpoints — unchanged

`/v1/health`, `/v1/ingest/start`, `/v1/ingest/status/{job_id}`, `/v1/search`, `/v1/styled-search`, `/v1/auth/*`, virtual try-on endpoints all carry forward exactly as they are on `main`. **Additive** per DEC-007.

---

## Slot-Filling Behavior

### Required-fields list is configurable

Required slots are driven by **settings**, not hardcoded in the system prompt:

```python
# src/config.py addition
required_search_fields: list[str] = ["gender", "occasion"]
```

v3.0 ships with `["gender", "occasion"]`. The required-fields list can be extended in future versions without any graph-code change — the `check_required_fields` tool reads it from settings.

### Required slots (v3.0)

| Slot | Allowed values | Default if user can't supply after MAX_ASK_USER attempts |
|---|---|---|
| `gender` | `women`, `men`, `unisex` | `"women"` |
| `occasion` | `wedding`, `party`, `casual`, `formal`, `festive`, `office`, `traditional` | `"casual"` |

### Optional slots (inferred by `enrich_query`, never asked)

| Slot | Allowed values | Source |
|---|---|---|
| `colors` | PRD v2 taxonomy | Inferred by `enrich_query` from user message |
| `garment_type` (a.k.a. `category`) | PRD v2 categories | Inferred by `enrich_query` from user message |

### Clarification flow

The agent's workflow (in YAML system prompt) is:

1. **Call `check_required_fields()`** — reads `state.gathered_slots`, compares against `REQUIRED_SEARCH_FIELDS`, returns `SlotCheckResult`.
2. **If `all_filled=False` AND `ask_user_count_in_history < MAX_ASK_USER (=3)`** → call `ask_user(question)` with ONE **consolidated** question covering ALL `missing_fields` in a single message. Example: *"To find the best looks for you, could you tell me: (1) is this for women's or men's wear, and (2) what's the occasion — wedding, party, casual, formal, festive, office, or traditional?"*
3. HITL middleware interrupts. Frontend renders one InterruptCard. User answers (one combined reply). Frontend resumes with `Command(resume={decisions:[{type:"respond", message:"..."}]})`.
4. The user's reply lands as the `ask_user` tool's return value. Agent **re-calls `check_required_fields`** to re-validate.
5. If still missing AND `ask_user_count < 3` → another consolidated ask of the still-missing slots.
6. **Cap at MAX_ASK_USER = 3.** On the 4th attempt (i.e., after 3 asks have already happened in history), the agent **applies defaults** for any still-missing required slot, tells the user transparently in the final reply (*"I went with women's casual since I couldn't get a clear answer — say so if you'd like different."*), and proceeds.

### Updating `gathered_slots`

`check_required_fields` only **reads** state. The agent (via `enrich_query`'s wrapper) is responsible for **populating** `state.gathered_slots` from the conversation history. Concretely, when the agent decides what slots it has, it passes them to `enrich_query(gender=..., occasion=...)` and the wrapper writes them into state via `Command(update={"gathered_slots": {...}})`. This keeps slot extraction implicit (LLM does it in its head from history) while making the resulting state machine-readable.

### Why this design

- **`check_required_fields` as a tool** makes slot validation explicit, observable in `tool_trace`, and testable in isolation. The agent has to actually call it — there's no implicit "did I check?" question.
- **Consolidated single ask per turn** cuts user friction: instead of "Is this women's? … OK and what occasion?" across 2 turns, one tightly-worded question covers both.
- **Settings-driven list** future-proofs adding more required fields (e.g., season, budget) without touching graph code.
- **Prompt-enforced cap** with `recursion_limit=10` as a hard safety net per LangGraph defaults.

---

## Tools

Five tools. All inputs and outputs are Pydantic-validated. Schemas live in `src/agent/schemas.py`. All tools follow the **parallel-wrapper pattern** (DEC-016) — they import from the unchanged original modules and add agent-specific concerns (state-writes, latency tracking, `tool_trace` entries).

### `check_required_fields() -> SlotCheckResult`

- **Body**: pure Python — reads `state.gathered_slots`, compares against `settings.required_search_fields`, returns a structured result. **No LLM call.**
- **Input schema**: none (uses `ToolRuntime` to access state).
- **Output schema**:
  ```python
  class SlotCheckResult(BaseModel):
      all_filled: bool
      missing_fields: list[str]
      gathered_slots: dict[str, str]
  ```
- **State-writes**: none (read-only).
- **When the agent calls it**: at the start of each turn AND after every `ask_user` interrupt resume.
- **Failure mode**: cannot fail (no I/O, no LLM, no external call).

### `ask_user(question: str) -> str`

- **Body**: not executed — `HumanInTheLoopMiddleware(interrupt_on={"ask_user": {"allowed_decisions": ["respond"]}})` raises an `Interrupt` before the tool runs. The user's reply (from the `respond` decision) becomes the tool's return value.
- **When the agent calls it**: ONLY when `check_required_fields` returned `all_filled=False` AND `ask_user_count_in_history < MAX_ASK_USER (=3)`.
- **System-prompt rule**: one CONSOLIDATED question per call, covering ALL missing fields in a single sentence. NOT one question per slot.
- **State-writes**: none directly. Side effect: the user's reply enters the conversation history; `enrich_query`'s wrapper later writes the extracted slots into `state.gathered_slots`.

### `enrich_query(raw_query: str, gender: str, occasion: str) -> EnrichedQuery`

- **Wraps**: `src/query_enrichment.py` (untouched). The existing function's signature is preserved; the wrapper composes a slot-aware prompt at the wrapper layer.
- **Prompt source**: `prompts/tool_prompts.yaml` → `query_enrichment_prompt` (loaded at startup by `prompt_loader.py`).
- **Input schema**: raw user query + slot values.
- **Output schema** (`EnrichedQuery`):
  ```python
  class EnrichedQuery(BaseModel):
      semantic_query: str
      inferred_colors: list[str]
      inferred_category: list[str]
      reasoning: str
  ```
- **State-writes** (via `Command(update=...)`):
  - `gathered_slots` ← merged with `{gender, occasion}` passed in
  - `current_filters` ← `SearchFilters(colors=inferred_colors, occasion=..., category=inferred_category, gender=...)`
  - `last_semantic_query` ← `semantic_query`
  - `tool_trace` ← append entry
- **Failure mode**: returns a fallback `EnrichedQuery` with raw query + slot values if the LLM call fails. Never raises. Failure recorded in `tool_trace[].error`.

### `search_products(semantic_query: str, filters: SearchFilters) -> list[Product]`

- **Wraps**: `src/search.py:run_search` (untouched).
- **Hard cap**: `top_k = MAX_RESULTS = 5`. The wrapper does NOT take `top_k` from the LLM — it's a setting. Prevents the LLM from circumventing the 5-result rule.
- **Mode policy**: wrapper passes `strict_mode=True` whenever any filter field is non-null; else `strict_mode=False`.
- **Input schema**:
  ```python
  class SearchFilters(BaseModel):
      colors: list[str] | None = None
      occasion: str | None = None
      category: list[str] | None = None
      gender: str | None = None
  ```
- **Output schema** (`Product`):
  ```python
  class Product(BaseModel):
      product_id: str
      image_path: str
      score: float
      category: str
      colors: list[str]
      occasion: str
      style_tags: list[str]
      caption: str
      gender: str | None
  ```
- **State-writes** (via `Command(update=...)`):
  - `last_products` ← returned products
  - `current_filters` ← `filters` (in case the agent passed different filters than `enrich_query` originally produced)
  - `tool_trace` ← append entry
- **Failure mode**: returns empty list + logs + error in `tool_trace[].error`; never raises. The agent's final reply handles the no-results UX (see Graceful Failure Modes).

### `curate_outfits(products: list[Product]) -> list[OutfitCombo]`

- **Wraps**: `src/stylist_agent.py:curate_outfits` (untouched).
- **Prompt source**: `prompts/tool_prompts.yaml` → `stylist_system_prompt`.
- **Output schema** (`OutfitCombo`) — **rationale required**:
  ```python
  class OutfitCombo(BaseModel):
      combo_id: str
      combo_rank: int                # 1..N (N ≤ 5)
      items: list[Product]           # top + bottom + accessories, OR a single full-body item
      rationale: str                 # MANDATORY — why this combo fits the user's stated slots
  ```
- **State-writes** (via `Command(update=...)`):
  - `last_combos` ← returned combos
  - `tool_trace` ← append entry
- **Failure mode**: if the stylist LLM fails, returns fallback combos formed by zipping top-3 products with `rationale="Stylist unavailable; showing raw results."` and records the error in `tool_trace`. If the input `products` list is empty, returns `[]` with no fallback combos — the agent's final reply handles the no-matches UX (see Graceful Failure Modes).

**Why "rationale required" across all curation outputs**: a recurring pattern in production agent apps (see DEC-010). Forces the LLM to justify its choice, gives the user transparency, and creates a hook for v3.1 evals (judge the rationale, not just the result).

---

## System Prompt

**Externalized to `prompts/agent_prompts.yaml`** under key `agent_system_prompt`. Loaded at startup by `src/agent/prompt_loader.py`. All canned user-facing strings (no-results message, more-count denial, thread-cap message, cap-fallback message) live in the same YAML so they stay consistent.

```yaml
# prompts/agent_prompts.yaml (excerpt)
agent_system_prompt: |
  You are a fashion stylist agent. You help users find outfits for occasions
  by searching a curated product catalog and proposing outfit combinations.

  Follow this workflow on every turn:

  1. CHECK SLOTS — Call check_required_fields. It returns all_filled,
     missing_fields, and gathered_slots based on the configured required-field
     list. Use this output, not your own inference, as ground truth.

  2. ASK IF NEEDED — If all_filled=False AND you have called ask_user fewer
     than 3 times in the conversation history:
     - Call ask_user ONCE with a CONSOLIDATED question covering ALL fields in
       missing_fields. Combine them into one short, friendly sentence.
     - Example for missing=["gender","occasion"]: "To find the best looks for
       you, could you tell me: (1) is this for women's or men's wear, and
       (2) what's the occasion — wedding, party, casual, formal, festive,
       office, or traditional?"
     - After the user replies, call check_required_fields AGAIN to revalidate.

  3. DEFAULTS AFTER CAP — If you have already called ask_user 3 times in this
     thread and slots are still missing, do NOT ask again. Apply defaults
     (gender="women", occasion="casual") and state your assumption in the
     final reply. Example: "I'll go with women's casual since I couldn't get
     a clear answer — say so if you'd like different."

  4. ENRICH — Call enrich_query(raw_query, gender, occasion). It returns the
     semantic query and inferred filters (colors, category). This also
     persists gathered_slots and current_filters into state.

  5. SEARCH — Call search_products(semantic_query, filters). The wrapper
     enforces a maximum of 5 products. You cannot override this.

  6. CURATE — Call curate_outfits(products). It returns up to 5 combos with
     rationale per combo.

  7. REPLY — Compose your final message:
     - Open with a short summary of slots used: "Here are N looks for a
       <gender> <occasion> occasion:"
     - Present each combo briefly — the rationale field speaks for itself.
     - If any defaults were applied, state them transparently.

  MULTI-TURN BEHAVIOR (when turn_count > 1):

  - VARIANT REQUESTS — "add red", "make it more formal", "show traditional",
    "different colors", "change to office wear":
      * Mutate state.current_filters appropriately based on the user's request.
      * Re-run enrich_query (if the query meaning changed) or skip directly to
        search_products with the updated filters.
      * Re-run curate_outfits on the new products.
      * Tell the user briefly what you changed: "I added red to the palette —
        here are the new looks."

  - "MORE COUNT" REQUESTS — "more options", "show me 2 more", "next page",
    "show different ones at the same filters":
      * REFUSE. Reply: "I show up to 5 results per search to keep choices
        focused. To see different looks, try changing a filter — for example
        a different color, occasion, or style."
      * Do NOT call search_products again.

  - ZERO-RESULT FROM VARIANT — If a variant request yields 0 products:
      * Reply: "I couldn't find matches for <changed filters>. Want to drop
        one of the constraints or try a different <color/occasion>?"

  - TURN-COUNT CAP — If state.turn_count > 20:
      * Reply: "We've covered a lot in this thread. To keep things
        responsive, please start a new chat thread for further looks."
      * Do not call any tools.

  NEVER:
  - Skip check_required_fields before deciding to search.
  - Call ask_user more than 3 times per thread.
  - Split a missing-fields question into multiple ask_user calls — always
    consolidate.
  - Override the 5-result cap.
  - Honor "more options" / pagination requests.
  - Invent products or rationales — only use tool outputs.
  - Mention tool names to the user.
```

The full file in `prompts/agent_prompts.yaml` additionally defines:

```yaml
no_results_message: |
  I couldn't find any matches for that query. Try changing the colors,
  occasion, or style — for example, "show me casual wear" or "try blue
  instead of yellow."

more_count_denial_message: |
  I show up to 5 results per search to keep choices focused. To see
  different looks, try changing a filter — for example a different color,
  occasion, or style.

thread_cap_message: |
  We've covered a lot in this thread. To keep things responsive, please
  start a new chat thread for further looks.

cap_fallback_message_template: |
  I'll go with {gender} {occasion} since I couldn't get a clear answer
  on those — let me know if you'd like something different.
```

---

## Multi-Turn Refinement

v3.0 supports follow-up turns within the same `thread_id`, but with **two strictly different rules** depending on what the user asks for. The agent decides which path applies based on the message content.

### Pathway A — Variant refinement (ALLOWED)

Triggers: the user wants the SAME number of results with DIFFERENT attributes.

Examples:
- "Add red as a color option"
- "Make it more formal"
- "Show traditional styles only"
- "Change the occasion to office wear"
- "Drop the embroidered ones"
- "Try blue instead of yellow"

Behavior:
1. Agent reads `state.current_filters` and `state.last_semantic_query`.
2. Agent mutates the filter set per the user's request (add/remove colors, change occasion, etc.).
3. Optionally re-calls `enrich_query` if the semantic meaning of the query changed substantially.
4. Calls `search_products` with the new filters (still capped at 5 results).
5. Calls `curate_outfits` on the new products.
6. Replies with a brief change summary: *"I added red to the palette — here are the new looks."*

### Pathway B — "More count" requests (REFUSED)

Triggers: the user wants MORE results at the same filters.

Examples:
- "More options"
- "Show me 2 more"
- "Next page"
- "Show different ones with the same filters"
- "Any more like these"

Behavior:
1. Agent does NOT call any tool.
2. Agent replies with the canned `more_count_denial_message` from `prompts/agent_prompts.yaml`: *"I show up to 5 results per search to keep choices focused. To see different looks, try changing a filter — for example a different color, occasion, or style."*

Rationale for refusing: keeps the demo predictable, keeps the result set small enough to scan, side-steps a pagination UI in v3.0. Pagination is explicitly listed as a v3.1 deferral.

### Pathway-conflict heuristic

If the user's message is ambiguous (e.g., *"more like these but in red"*) — that's pathway A (variant), not B. The "in red" qualifier means filters change. The system prompt instructs the agent to treat any attribute-change qualifier as variant; pure "more" with no attribute change is the only thing that triggers pathway B.

### Zero-result variant

If a variant request returns 0 products:
- Agent replies with a graceful no-match message naming what was filtered to zero: *"I couldn't find matches for women's traditional office wear in red. Want to drop one of the constraints or try a different color?"*
- Does NOT silently fall back or invent products.

### Turn-count cap

When `state.turn_count > 20`, agent stops engaging variant or pagination requests and replies with `thread_cap_message`: *"We've covered a lot in this thread. To keep things responsive, please start a new chat thread for further looks."*

`SummarizationMiddleware` (which would let conversations go much longer without context bloat) is **deferred to v3.1** — see Non-Goals.

---

## Prompt Management

All prompts in v3.0 live in `prompts/*.yaml`, loaded at startup. Two files:

### `prompts/agent_prompts.yaml`

| Key | Used by | Purpose |
|---|---|---|
| `agent_system_prompt` | `src/agent/graph.py` | The full numbered workflow shown above |
| `no_results_message` | `agent_node` final reply | Canned message when search returns 0 |
| `more_count_denial_message` | `agent_node` final reply | Canned message for pathway B refusal |
| `thread_cap_message` | `agent_node` final reply | Canned message when `turn_count > 20` |
| `cap_fallback_message_template` | `agent_node` final reply | Template with `{gender}` / `{occasion}` placeholders for cap-fallback transparency |

### `prompts/tool_prompts.yaml`

| Key | Used by | Purpose |
|---|---|---|
| `stylist_system_prompt` | `src/agent/tools.py:curate_outfits` wrapper | Moved out of `src/stylist_agent.py`; same content, just relocated |
| `query_enrichment_prompt` | `src/agent/tools.py:enrich_query` wrapper | Moved out of `src/query_enrichment.py`; wrapper passes it to the underlying function |

### Loader

```python
# src/agent/prompt_loader.py — sketch
import yaml
from functools import lru_cache
from pathlib import Path

@lru_cache(maxsize=2)
def _load(file_name: str) -> dict[str, str]:
    return yaml.safe_load(Path("prompts", file_name).read_text())

def get_agent_prompt(key: str) -> str: return _load("agent_prompts.yaml")[key]
def get_tool_prompt(key: str) -> str:  return _load("tool_prompts.yaml")[key]
```

### Versioning

Implicit via git — every prompt change is a code change. v3.1 will layer LangSmith Hub on top for prompt-registry features (named versions, A/B). The YAML loader's interface stays stable.

### Why YAML, not Python constants

- Treats prompts as **config**, not code — clear separation of concerns.
- Easier to diff prompt changes in a PR review.
- Hot-reloading possible later (not in v3.0).
- Sets up v3.1 LangSmith Hub migration cleanly — only the loader changes.

---

## Graceful Failure Modes

The agent must never crash, return raw stack traces, or invent fake content. All failure scenarios resolve into clean user-facing messages.

| Failure | Behavior |
|---|---|
| `check_required_fields` returns missing slots, MAX_ASK_USER reached | Apply defaults from settings; tell user transparently via `cap_fallback_message_template`. |
| `enrich_query` LLM call fails | Wrapper returns fallback `EnrichedQuery` with raw query + slot values; logs to `tool_trace[].error`. Agent proceeds to search with whatever filters it can derive. |
| `search_products` returns 0 products | Tool returns `[]`. Agent skips `curate_outfits` and replies with `no_results_message`, optionally enriched with the variant-specific naming ("I couldn't find matches for X + Y..."). |
| `curate_outfits` LLM call fails | Wrapper returns fallback combos from top-3 products with `rationale="Stylist unavailable; showing raw results."` Logs error. |
| `curate_outfits` receives empty product list | Returns `[]`. Agent handles UX (see "0 products" row above). |
| User asks for "more count" | Agent refuses with `more_count_denial_message`. No tool call. |
| Variant request yields 0 products | Agent replies with constraint-aware no-match suggestion (suggest dropping a filter). |
| `turn_count > 20` | Agent replies with `thread_cap_message`. No tool call. |
| `recursion_limit (=10)` exceeded | LangGraph raises `GraphRecursionError`. FastAPI handler catches it, returns 500 with body `{"error": "Agent took too many steps. Please start a new thread."}` |
| HITL interrupt resume with wrong `thread_id` | Checkpointer returns no state; FastAPI returns 404. |

All canned messages are loaded from `prompts/agent_prompts.yaml` so they stay consistent across the codebase. The frontend renders them as ordinary assistant messages — no special UX needed for failure modes.

---

## Frontend Changes

### New: side ChatPanel in `frontend/`

- Embedded into the existing search screen as a side panel (NOT a new route). See DEC-008.
- Components: `ChatPanel.jsx` (input + message list), `MessageBubble.jsx` (user / assistant / system messages), `InterruptCard.jsx` (renders pending `ask_user` question with a dedicated reply input).
- State: `chatState.js` manages `thread_id` (client-generated UUID, regenerated per new conversation), `messages` array (local mirror), `pendingInterrupt` (the current `pending_action` if any).
- API client: `chatApi.js` exposes `sendMessage(text)`, `sendResume(replyText)`, and `getThread(threadId)` — wraps `/v1/chat` and `/v1/chat/threads/{id}`.

### Unchanged

The existing search UI on the same screen continues to work via `/v1/search` and `/v1/styled-search`. No code in the legacy search components is touched in v3.0.

### Deprecated (cleanup in v3.1)

`src/static/` static HTML files are declared **deprecated** in this PRD. The FastAPI mount that serves them stays in v3.0 to avoid touching `main.py`; both go away in v3.1's cleanup PR.

---

## Configuration (.env additions)

```
# Agent (v3.0 additions)
AGENT_MODEL_NAME=gemini-2.5-flash
AGENT_RECURSION_LIMIT=10
AGENT_MAX_ASK_USER=3
AGENT_MAX_RESULTS=5
AGENT_MAX_TURNS=20
AGENT_DEFAULT_GENDER=women
AGENT_DEFAULT_OCCASION=casual

# Required-field list — comma-separated. Drives check_required_fields.
AGENT_REQUIRED_SEARCH_FIELDS=gender,occasion
```

All other existing environment variables are unchanged.

---

## Security (v3.0)

Carries forward PRD v2's security model unchanged for the existing endpoints. For `/v1/chat`:

- `X-API-Key` required (same middleware).
- `thread_id` is treated as an opaque client-provided string — no leakage between threads (the checkpointer key-scopes everything).
- User message length capped at 500 chars at the FastAPI handler level. Longer inputs get a 400.
- No prompt-injection guardrail in v3.0 — that lands in v3.1 with Guardrails-AI / NeMo.
- All Pydantic-typed tool inputs and outputs reject malformed LLM responses at the boundary.

---

## Non-Functional Requirements (v3.0 minimum)

| Requirement | Target |
|---|---|
| Initial test scale | Up to ~50 concurrent threads in dev (in-memory checkpointer is fine) |
| `/v1/chat` p95 latency (happy path, no interrupt) | < 8 s end-to-end. Happy path is ~5 `agent_node` Flash calls (one per ReAct iteration) + 1 internal Flash call in `enrich_query` + 1 internal Pro call in `curate_outfits` + 1 Pinecone query. `check_required_fields` is pure Python (~ms). |
| `/v1/chat` p95 latency (variant refinement turn) | < 6 s. Slot check passes immediately; runs enrich → search → stylist with prior context. |
| `/v1/chat` p95 latency (interrupt response only) | < 2 s (slot check + 1 Flash call to compose the consolidated question). |
| Recursion safety | `recursion_limit=10`; no run exceeds 10 agent ↔ tools cycles |
| Auth | `X-API-Key` (unchanged) |
| Logging | Python built-in `logging`, structured fields manually included (`request_id`, `thread_id`, `tool_name`, `iteration`, `latency_ms`). Structlog migration is v3.1. |
| Observability | Console logs only in v3.0. LangSmith tracing is v3.1. |
| Testing | Manual via Swagger + React chat panel. Automated tests are v3.1. |

---

## Testing Strategy (v3.0)

**Manual acceptance scenarios** (all via Swagger UI + the React chat panel):

### Single-turn scenarios

1. **Happy path, slots inferable**: User sends "yellow dress for a wedding". Agent calls `check_required_fields` → `all_filled=True` (both slots inferable). No `ask_user`. Searches, returns ≤5 combos with rationale.
2. **Consolidated single ask**: User sends "something for tomorrow". Agent calls `check_required_fields` → `missing_fields=["gender","occasion"]`. Agent calls `ask_user` ONCE with a consolidated question covering both. User replies *"women's wedding"* in one message. Agent re-validates, all filled, proceeds to search.
3. **Cap fallback**: User sends "something nice". Agent asks the consolidated question 3 times across the thread; user gives unclear replies each time. After the 3rd ask, agent applies defaults `women` + `casual`, returns combos, tells user *"I'll go with women's casual since I couldn't get a clear answer — say so if you'd like different."*
4. **No results**: User sends a query that returns zero products. Tool returns `[]`. Agent's final reply is the `no_results_message` canned text, with a suggestion to vary filters.
5. **Concurrent threads**: Two `thread_id`s do not bleed state into each other. Verified by interleaving turns from both.
6. **Server restart**: Existing threads lost; new threads start fresh. Acceptable v3.0 behavior.
7. **Invalid request**: Both `message` and `resume` present → 400. Neither present → 400.

### Multi-turn scenarios (new)

8. **Variant — add color**: Turn 1: "yellow dress for wedding", 3 combos returned. Turn 2: "add red as a color option". Agent reads `state.current_filters`, adds "red" to colors, re-searches, returns NEW combos (some include red), reply opens *"I added red to the palette — here are the new looks."*
9. **Variant — change occasion**: Turn 1: "show me office wear", combos returned. Turn 2: "make it more formal". Agent mutates `current_filters.occasion` to "formal", re-runs `enrich_query` + `search_products` + `curate_outfits`, replies with change summary.
10. **Pagination denial**: Turn 1: results returned. Turn 2: "show me 2 more options". Agent does NOT call any tool. Returns canned `more_count_denial_message` verbatim.
11. **Pagination denial — synonyms**: Same as 10 but user says "more like these" or "next page". Same denial.
12. **Zero-result variant**: Turn 1: wedding results. Turn 2: "make it traditional only AND show in red AND must be office wear" (overconstrained). Agent searches, gets 0 products, replies with constraint-aware no-match message + suggestion to drop a filter.
13. **Turn-count cap**: Manually drive `state.turn_count` to 21 (via 21 turns or test harness). Next user message → agent replies with `thread_cap_message`. No tool call.
14. **Mixed variant + count**: User says "more like these but in red". Variant qualifier wins — agent re-searches with `colors=[..., "red"]`, returns new combos. Reply mentions the color change.

### Observability scenarios

15. **`tool_trace` populated**: After a full happy-path turn, `GET /v1/chat/threads/{id}` shows `tool_trace` with one entry per tool call (name + latency_ms).
16. **`request_id` propagation**: Every response has a unique `request_id`. Same `thread_id` across turns gets distinct `request_id`s (one per HTTP request).
17. **Failure recorded**: Force `curate_outfits` to fail (mock Gemini Pro outage). Final reply still returns fallback combos. `tool_trace` entry for `curate_outfits` has a non-null `error` field.

---

## v3.1+ Roadmap (deferred items, in order)

| Phase | Pillar | Scope |
|---|---|---|
| v3.1 | **Observability** | LangSmith tracing wired (env vars, project name, thread tagging), `structlog` migration, per-node latency metrics emitted, dashboards. v3.0's in-state `tool_trace` is the bridging signal. |
| v3.1 | **Guardrails** | Guardrails-AI input rail (prompt injection, length cap), output rail (schema enforcement); evaluate NeMo for topical rail ("fashion-only") |
| v3.1 | **Evals** | LangSmith dataset of 10–20 golden conversations, automated regression run, judge the `rationale` field and the slot-recall accuracy |
| v3.1 | **Pagination / "more options"** | Lift the 5-result hard cap; introduce paged results with a paging UI. Until then, requests are explicitly refused. |
| v3.1 | **Combo-swap refinement** | "Swap the top of combo 2" — finer-grained mutation than variant refinement |
| v3.1 | **Conversation summarization** | `SummarizationMiddleware` so threads can exceed 20 turns without context bloat |
| v3.1 | **LangSmith Hub for prompts** | Layer prompt versioning + A/B on top of the YAML registry shipped in v3.0 |
| v3.1 | **Static HTML cleanup** | Delete `src/static/`, remove FastAPI mount, README updates |
| v3.2 | **Deployment** | Dockerfile, docker-compose, deploy to Railway or Cloud Run, smoke tests; persistent checkpointer (`AsyncPostgresSaver`) if multi-instance |
| v3.2 | **Streaming** | SSE-stream the agent's final reply to the chat panel for real-time UX |
| v3.x | **Rate limiting & token budgets** | `slowapi` on `/v1/chat`, per-key daily token budget via Redis |
| v3.x | **Multi-provider experiment** | Evaluate Claude / OpenAI for `agent_node` against Gemini; multi-provider abstraction |
| v3.x | **Multi-agent supervisor migration** | Revisit only if tool count exceeds ~6 or domains cluster (per DEC-010) |

Each phase gets its own PRD increment, not a rewrite of v3.

---

## Decision Log (summary — full ADRs in `learnings/design-decisions-log.md`)

| # | Decision | Choice |
|---|---|---|
| DEC-001 | Branch strategy | Freeze on `llm-implementation`, work on `agentic-implementation` |
| DEC-002 | PRD v3.0 scope | Agent core in v3.0; remaining NFRs to v3.1+ |
| DEC-003 | UX shape (historical) | Originally single-shot clarify-then-search — SUPERSEDED by DEC-013 |
| DEC-004 | Session model | `thread_id` + LangGraph `InMemorySaver` |
| DEC-005 | Required slots (initial) | `gender` + `occasion` — list now config-driven per DEC-014 |
| DEC-006 | Clarify LLM | Gemini 2.5 Flash, single-provider |
| DEC-007 | API surface | Additive — keep `/v1/search` + `/v1/styled-search`, add `/v1/chat` |
| DEC-008 | Frontend | Side ChatPanel embedded in existing search screen |
| DEC-009 | Cap fallback (initial) | Safe defaults + transparent message; N was 2 — superseded by DEC-014 (N=3) |
| DEC-010 | Graph topology | **Single-agent ReAct + 5 tools**, NOT multi-agent supervisor |
| DEC-011 | HITL pattern | `HumanInTheLoopMiddleware` + `ask_user` tool, `respond` decision type |
| DEC-012 | Documentation source | LangChain docs MCP for all framework claims |
| DEC-013 | Multi-turn refinement | Pulled into v3.0; two pathways — variant ALLOWED, "more count" DENIED; 5-result hard cap |
| DEC-014 | Slot validation tool | New `check_required_fields` tool; consolidated single ask; MAX_ASK_USER=3; required-fields config-driven |
| DEC-015 | Prompt externalization | YAML files in `prompts/` in v3.0 (not deferred) |
| DEC-016 | Tool wrappers | Parallel-wrapper pattern — original modules untouched, `src/agent/tools.py` is the only place that imports them |

---

## Assumptions

- LangChain ≥ 0.3.x and LangGraph ≥ 0.2.x are stable for `create_agent`, `HumanInTheLoopMiddleware`, and `state_schema` extension. (Verified via the docs MCP at session start.)
- Existing `src/query_enrichment.py`, `src/search.py`, `src/stylist_agent.py` interfaces stay stable. Wrappers do not modify them (DEC-016).
- Stylist prompt and query-enrichment prompt can be cleanly extracted from Python source into YAML without changing behavior (verified by reading both files during design).
- The Gemini 2.5 Flash + 2.5 Pro split is cost-effective at prototype scale.
- Single-tenant: no multi-user isolation needed beyond per-thread keying in v3.0.
- React frontend (`frontend/`) is the canonical UI; `src/static/` is deprecated.
- Five products per search is enough for the demo without pagination. Validated against the manual acceptance scenarios.
- 20 turns per thread is a safe cap given vanilla history strategy and Gemini Flash's context window.

---

## Milestones (v3.0 implementation order — to be detailed in the implementation plan)

1. **Agent scaffolding**: `src/agent/` package skeleton, `FashionAgentState` + Pydantic schemas in `schemas.py`, `prompt_loader.py`.
2. **Prompt extraction**: move stylist + enrichment prompts from Python into `prompts/tool_prompts.yaml`; create `prompts/agent_prompts.yaml` with all agent strings.
3. **Tool wrappers** (parallel-wrapper pattern, DEC-016): `check_required_fields`, `ask_user`, `enrich_query`, `search_products`, `curate_outfits` — each a thin `@tool` over existing modules with state-writes via `Command(update=...)`.
4. **Graph wiring**: `create_agent` + `HumanInTheLoopMiddleware` + `InMemorySaver` + `state_schema=FashionAgentState` in `graph.py`.
5. **FastAPI route**: `/v1/chat` handler in `routes.py` supporting both request shapes; `/v1/chat/threads/{id}` diagnostic endpoint; observability fields in responses.
6. **Frontend ChatPanel**: side panel + interrupt card + chat state in `frontend/src/chat/`. Handle two response shapes.
7. **Manual E2E validation**: walk through all 17 acceptance scenarios above. Update PRD and decision log with any discoveries.

Detailed task breakdown for each milestone happens in the implementation plan (next phase, via `superpowers:writing-plans`).
