# AI Fashion Designer v3.0 — Implementation Plan

> **Status:** Draft → Locked on user approval
> **Parent spec:** [`specs/PRD_v3_Agentic.md`](./PRD_v3_Agentic.md) (locked)
> **Branch:** `agentic-implementation`
> **Companion docs:** `learnings/design-decisions-log.md` (ADR trail), `learnings/project-build-journal.md` (concept journal), `.claude-session-log.md` (session narrative)

> **For the executor (read before starting):**
> 1. Run this plan via **`superpowers:subagent-driven-development`** — dispatch a fresh implementer subagent per task with the task's full text + context, then a spec-compliance reviewer, then a code-quality reviewer, then commit. Do not batch.
> 2. Every task's **Verification** block is non-negotiable per **`superpowers:verification-before-completion`** — run the literal command, paste actual output, then claim done. No "should pass."
> 3. **One task → one commit.** Commit message references the task number and the PRD section it implements.
> 4. Every framework claim is cited against the LangChain docs MCP (`mcp__docs-langchain__search_docs_by_lang_chain` / `mcp__docs-langchain__query_docs_filesystem_docs_by_lang_chain`) per **DEC-012**. If a docs lookup contradicts this plan, stop and escalate.
> 5. After all 7 milestones pass: run **`/ultrareview`** on the branch, then **`/security-review`**, then `superpowers:finishing-a-development-branch`.

---

## Goal

Ship the v3.0 single-agent ReAct chat surface: `POST /v1/chat` + side `ChatPanel` in the React frontend, powered by `langchain.agents.create_agent` + `HumanInTheLoopMiddleware` + `InMemorySaver` + a custom `FashionAgentState`, with five `@tool`-decorated wrappers over the existing vision-first RAG pipeline.

## Architecture (one line each)

- **Runtime:** `create_agent(model=Gemini-2.5-Flash, tools=[5 wrappers], state_schema=FashionAgentState, middleware=[HITL], checkpointer=InMemorySaver, system_prompt=YAML)` — DEC-010, DEC-011.
- **Pattern:** parallel-wrapper (DEC-016) — `src/agent/tools.py` is the ONLY new module that imports `src/search.py`, `src/query_enrichment.py`, `src/stylist_agent.py`. Originals stay byte-for-byte intact.
- **Prompts:** all in `prompts/*.yaml`, loaded by `src/agent/prompt_loader.py` — DEC-015.
- **API surface:** additive — `/v1/chat` + `/v1/chat/threads/{id}` added; `/v1/search`, `/v1/styled-search`, ingestion, auth all unchanged — DEC-007.

## Tech-stack delta from current

Add to `requirements.txt`: `langchain`, `langgraph`, `langchain-google-genai`, `pyyaml`. Nothing removed.

## Task summary (at-a-glance)

| # | Task | Deliverable | PRD section | Commit prefix |
|---|---|---|---|---|
| 1.1 | Dependencies + agent config | `requirements.txt` + 8 `Settings` fields + `.env.example` | §Configuration | `chore(agent):` |
| 1.2 | Pydantic schemas + `FashionAgentState` | `src/agent/schemas.py` (10 models, state with reducer) | §State, §Tools | `feat(agent):` |
| 1.3 | YAML prompt loader | `src/agent/prompt_loader.py` | §Prompt Management | `feat(agent):` |
| 2.1 | `tool_prompts.yaml` | Stylist + enrichment prompts externalized | §Prompt Management | `feat(prompts):` |
| 2.2 | `agent_prompts.yaml` | Agent system prompt + 4 canned messages | §System Prompt | `feat(prompts):` |
| 3.1 | `check_required_fields` tool + `_trace` helper | First tool in `src/agent/tools.py` | §Tools, DEC-014 | `feat(agent):` |
| 3.2 | `ask_user` HITL stub | Tool stub that raises if uninterrupted | §Tools, DEC-011 | `feat(agent):` |
| 3.3 | `enrich_query` wrapper + `gathered_slots` reducer | Wrapper writes slots + filters + semantic query | §Tools, DEC-016 | `feat(agent):` |
| 3.4 | `search_products` wrapper | 5-result hard cap; strict-mode policy | §Tools, DEC-013 | `feat(agent):` |
| 3.5 | `curate_outfits` wrapper | Rationale-required combos + empty/error fallbacks | §Tools | `feat(agent):` |
| 4.1 | Graph wiring | `src/agent/graph.py` — `create_agent` + HITL + checkpointer + recursion cap | §Architecture, DEC-010, DEC-011 | `feat(agent):` |
| 5.1 | `POST /v1/chat` (both shapes) | `src/agent/routes.py` + router included in `src/main.py` | §Public APIs | `feat(api):` |
| 5.2 | `GET /v1/chat/threads/{id}` diagnostic | Thread state inspection endpoint | §Public APIs | `feat(api):` |
| 6.1 | Chat API client + state hook | `frontend/src/chat/chatApi.js` + `chatState.js` | §Frontend, DEC-008 | `feat(frontend):` |
| 6.2 | `ChatPanel` + `InterruptCard` | Side panel docked into existing search screen | §Frontend, DEC-008 | `feat(frontend):` |
| 7.1 | Walk 17 acceptance scenarios | Pass/fail trace per PRD §Testing Strategy | §Testing Strategy | `fix(agent):` (only if needed) |

---

## Milestone ordering rationale

Scaffolding → prompts → tools → graph → API → frontend → E2E validation. Each milestone produces something verifiable on its own and ratchets the agent up one layer (schemas → prompt registry → callable tools → orchestrated agent → HTTP surface → UX → acceptance test). Alternatives considered (build graph first, defer prompts; vertical happy-path slice first) rejected because (a) graph won't compile without tools or prompts, (b) vertical slice would force premature stubs that get rewritten. See **DEC-017** in `learnings/design-decisions-log.md`.

---

## Milestone 1 — Agent scaffolding

Implements PRD §Project Structure, §State, §Configuration.

### Task 1.1 — Dependencies + agent config

**PRD section:** §Configuration; §Tech Stack.

**Files:**
- Modify: `requirements.txt` — append `langchain>=0.3`, `langgraph>=0.2`, `langchain-google-genai>=2.0`, `pyyaml>=6.0`. Pin to the docs-MCP-confirmed minor versions.
- Modify: `src/config.py` — add eight `Settings` fields per PRD §Configuration:
  - `agent_model_name: str = "gemini-2.5-flash"`
  - `agent_recursion_limit: int = 10`
  - `agent_max_ask_user: int = 3`
  - `agent_max_results: int = 5`
  - `agent_max_turns: int = 20`
  - `agent_default_gender: str = "women"`
  - `agent_default_occasion: str = "casual"`
  - `agent_required_search_fields: list[str] = Field(default_factory=lambda: ["gender", "occasion"])` — accept comma-separated env via a `@field_validator("agent_required_search_fields", mode="before")` that splits a string.
- Modify: `.env.example` — append the eight keys with default values commented.

**Deliverable:** `Settings()` loads with the new defaults; server still boots.

**Verification:**
```
pip install -r requirements.txt
python -c "from src.config import Settings; s=Settings(); print(s.agent_model_name, s.agent_max_results, s.agent_required_search_fields)"
uvicorn src.main:app --port 8000 &
sleep 3 && curl -s http://localhost:8000/v1/health && kill %1
```
Expected stdout: `gemini-2.5-flash 5 ['gender', 'occasion']`; health returns 200 with the existing payload.

**Commit:** `chore(agent): add v3.0 agent settings and langgraph deps (PRD §Configuration)`

---

### Task 1.2 — Pydantic schemas + `FashionAgentState`

**PRD section:** §State; §Tools (IO schemas); §Public APIs (request/response shapes).

**Files:**
- Create: `src/agent/__init__.py` (empty).
- Create: `src/agent/schemas.py` — define **exactly** the Pydantic models named in the PRD:
  - `ToolTraceEntry(BaseModel)` — `tool_name: str`, `latency_ms: int`, `error: str | None = None`.
  - `SlotCheckResult(BaseModel)` — `all_filled: bool`, `missing_fields: list[str]`, `gathered_slots: dict[str, str]`.
  - `SearchFilters(BaseModel)` — `colors: list[str] | None = None`, `occasion: str | None = None`, `category: list[str] | None = None`, `gender: str | None = None`.
  - `EnrichedQuery(BaseModel)` — `semantic_query: str`, `inferred_colors: list[str]`, `inferred_category: list[str]`, `reasoning: str`.
  - `Product(BaseModel)` — `product_id, image_path, score, category, colors, occasion, style_tags, caption, gender` per PRD §Tools `search_products`.
  - `OutfitCombo(BaseModel)` — `combo_id, combo_rank, items: list[Product], rationale: str` (rationale required).
  - `ChatRequest`, `ChatResumeDecision`, `ChatResumeRequest` (the two request shapes from PRD §Public APIs).
  - `PendingAction`, `ChatFinalResponse`, `ChatInterruptResponse`.
  - `FashionAgentState(AgentState)` — extends `langchain.agents.middleware.AgentState`. Fields per PRD §State, with **`tool_trace: Annotated[list[ToolTraceEntry], operator.add]`** so concurrent tool writes append rather than overwrite (LangChain docs: `oss/python/langchain/tools.mdx` → "Update state" — *"consider defining a reducer for those fields"*).

**Deliverable:** module imports cleanly; schemas reject malformed inputs.

**Verification:**
```
python -c "
from src.agent.schemas import FashionAgentState, Product, OutfitCombo, SlotCheckResult
Product(product_id='p1', image_path='x', score=0.5, category='dress', colors=['red'], occasion='wedding', style_tags=[], caption='c', gender='women')
try: OutfitCombo(combo_id='c', combo_rank=1, items=[])
except Exception as e: print('OK missing rationale rejected:', type(e).__name__)
print('OK all schemas import')
"
```
Expected: `OK missing rationale rejected: ValidationError` then `OK all schemas import`.

**Commit:** `feat(agent): add FashionAgentState and tool IO schemas (PRD §State, §Tools)`

---

### Task 1.3 — YAML prompt loader

**PRD section:** §Prompt Management.

**Files:**
- Create: `prompts/.gitkeep` (folder populated in Milestone 2).
- Create: `src/agent/prompt_loader.py`:
  ```python
  import yaml
  from functools import lru_cache
  from pathlib import Path

  _PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"

  @lru_cache(maxsize=2)
  def _load(file_name: str) -> dict[str, str]:
      return yaml.safe_load((_PROMPTS_DIR / file_name).read_text())

  def get_agent_prompt(key: str) -> str:
      return _load("agent_prompts.yaml")[key]

  def get_tool_prompt(key: str) -> str:
      return _load("tool_prompts.yaml")[key]
  ```
- Missing key → `KeyError` propagates (loud-fail at startup is the desired behavior).

**Deliverable:** loader importable; surfaces clear errors when YAML is absent.

**Verification:**
```
python -c "from src.agent.prompt_loader import get_agent_prompt; get_agent_prompt('x')" || echo "OK loader errors as expected (YAML not yet created)"
```
Expected: a `FileNotFoundError` mentioning `prompts/agent_prompts.yaml`, followed by `OK loader errors as expected`.

**Commit:** `feat(agent): add YAML prompt loader (PRD §Prompt Management, DEC-015)`

---

## Milestone 2 — Prompt externalization (DEC-015)

### Task 2.1 — `prompts/tool_prompts.yaml`

**PRD section:** §Prompt Management → `tool_prompts.yaml` table.

**Files:**
- Read first: `src/query_enrichment.py` and `src/stylist_agent.py` — locate the existing Python-embedded prompt constants verbatim.
- Create: `prompts/tool_prompts.yaml` with exactly two keys:
  - `query_enrichment_prompt: |` ← byte-for-byte the existing constant.
  - `stylist_system_prompt: |` ← byte-for-byte the existing constant.
- **Do NOT modify** `src/query_enrichment.py` or `src/stylist_agent.py` in this task — that touches DEC-016. Wrappers in Milestone 3 will pass the loaded prompt in via an optional kwarg.

**Deliverable:** the YAML round-trips both prompts unchanged.

**Verification:**
```
python -c "
from src.agent.prompt_loader import get_tool_prompt
s = get_tool_prompt('stylist_system_prompt')
q = get_tool_prompt('query_enrichment_prompt')
print('stylist_len', len(s), 'enrich_len', len(q))
assert len(s) > 200 and len(q) > 100, 'prompts look truncated'
print('OK')
"
```
Expected: non-zero lengths, then `OK`. Spot-check first 80 chars of each match the originals.

**Commit:** `feat(prompts): externalize tool prompts to YAML (DEC-015)`

---

### Task 2.2 — `prompts/agent_prompts.yaml`

**PRD section:** §System Prompt (the full numbered-workflow block + the four canned messages).

**Files:**
- Create: `prompts/agent_prompts.yaml` with five keys copied **verbatim** from PRD §System Prompt:
  - `agent_system_prompt` — full numbered workflow (steps 1–7 + MULTI-TURN BEHAVIOR + NEVER list).
  - `no_results_message`
  - `more_count_denial_message`
  - `thread_cap_message`
  - `cap_fallback_message_template` — must contain literal `{gender}` and `{occasion}` placeholders.

**Deliverable:** all five keys load and lengths sanity-check.

**Verification:**
```
python -c "
from src.agent.prompt_loader import get_agent_prompt as g
keys = ['agent_system_prompt','no_results_message','more_count_denial_message','thread_cap_message','cap_fallback_message_template']
for k in keys: print(k, len(g(k)))
t = g('cap_fallback_message_template')
assert '{gender}' in t and '{occasion}' in t, 'template placeholders missing'
print('OK')
"
```
Expected: five non-zero lengths then `OK`. `agent_system_prompt` length should exceed 1500 chars.

**Commit:** `feat(prompts): add agent system prompt and canned messages (PRD §System Prompt)`

---

## Milestone 3 — Tool wrappers (parallel-wrapper pattern, DEC-016)

All five wrappers live in `src/agent/tools.py`. Shared `_trace` context manager defined at the top of the file (no extra module). Every wrapper returns a `Command(update={...})` containing both a `ToolMessage` (so the agent sees the tool's output) and the state-field updates per PRD §Tools.

Reducer note: the `operator.add` reducer on `tool_trace` (added in Task 1.2) is what makes `Command(update={"tool_trace": [entry]})` append rather than replace. If a task in this milestone tries to update a field that doesn't have a reducer and isn't the message list, it will overwrite — desired for `last_products` / `last_combos` / `current_filters`, undesired for `gathered_slots`. **Add a dict-merge reducer to `gathered_slots`** in Task 3.3 (see below).

### Task 3.1 — `check_required_fields` tool + shared `_trace` helper

**PRD section:** §Tools → `check_required_fields`.

**Files:**
- Create: `src/agent/tools.py` with:
  - Imports + shared `_trace` context manager (yields a mutable dict; captures `tool_name`, `latency_ms`, `error`).
  - `@tool` `check_required_fields(runtime: ToolRuntime) -> Command`:
    - Reads `runtime.state.get("gathered_slots", {})`.
    - Compares against `settings.agent_required_search_fields`.
    - Builds `SlotCheckResult(...)`.
    - Returns `Command(update={"messages": [ToolMessage(content=result.model_dump_json(), tool_call_id=runtime.tool_call_id)], "tool_trace": [ToolTraceEntry(**entry)]})`.
    - Cannot fail (pure Python).

**Deliverable:** tool importable; standalone invocation returns a `Command` whose update carries a `SlotCheckResult` showing both default-required slots missing.

**Verification:**
```
python -c "
from src.agent.tools import check_required_fields
out = check_required_fields.invoke({}, config={'configurable':{'thread_id':'t'}})
print(out)
"
```
Expected: `Command(update={...})` whose `messages` ToolMessage content includes `"all_filled": false` and `"missing_fields": ["gender", "occasion"]`.

**Commit:** `feat(agent): add check_required_fields tool and _trace helper (PRD §Tools, DEC-014)`

---

### Task 3.2 — `ask_user` tool stub

**PRD section:** §Tools → `ask_user`; DEC-011.

**Files:**
- Modify: `src/agent/tools.py` — append:
  ```python
  @tool
  def ask_user(question: str) -> str:
      """Ask the user a single consolidated clarifying question that covers ALL missing required slots."""
      raise RuntimeError("ask_user body must never execute — HITL middleware should have intercepted this call")
  ```
- Docstring is the LLM-facing description. The guard-RuntimeError catches misconfiguration in Milestone 4.

**Deliverable:** tool importable; direct invocation raises the guard.

**Verification:**
```
python -c "
from src.agent.tools import ask_user
try: ask_user.invoke({'question':'x'})
except RuntimeError as e: print('OK guard fired:', e)
"
```
Expected: `OK guard fired: ask_user body must never execute …`.

**Commit:** `feat(agent): add ask_user HITL tool stub (PRD §Tools, DEC-011)`

---

### Task 3.3 — `enrich_query` wrapper + `gathered_slots` reducer

**PRD section:** §Tools → `enrich_query`; §Slot-Filling Behavior → "Updating `gathered_slots`".

**Files:**
- Modify: `src/agent/schemas.py` — change `gathered_slots` to use a dict-merge reducer so successive enrich calls accumulate slots:
  ```python
  def _merge_dict(a: dict, b: dict) -> dict: return {**a, **b}
  ...
  gathered_slots: Annotated[dict[str, str], _merge_dict]
  ```
- Modify (minimal, DEC-016-compatible): `src/query_enrichment.py` — if the existing prompt is a module-level constant baked into a function body, add an optional kwarg `system_prompt: str | None = None` defaulting to the existing constant. No behavior change for existing callers. If the existing function already accepts an externally-supplied prompt, skip the modification.
- Modify: `src/agent/tools.py` — append `@tool enrich_query(raw_query: str, gender: str, occasion: str) -> Command`:
  - Calls `get_tool_prompt("query_enrichment_prompt")` and passes it to the underlying function.
  - On success builds an `EnrichedQuery`, then `Command(update={"messages":[ToolMessage(content=enriched.model_dump_json(), tool_call_id=runtime.tool_call_id)], "gathered_slots": {"gender": gender, "occasion": occasion}, "current_filters": SearchFilters(colors=enriched.inferred_colors, occasion=occasion, category=enriched.inferred_category, gender=gender), "last_semantic_query": enriched.semantic_query, "tool_trace": [entry]})`.
  - On failure returns a fallback `EnrichedQuery(semantic_query=raw_query, inferred_colors=[], inferred_category=[], reasoning="enrichment failed; using raw query")` + records `entry["error"]`. Never raises.

**Deliverable:** wrapper works against the live Gemini key; legacy `/v1/styled-search` regression-checked.

**Verification:**
```
python -c "
from src.agent.tools import enrich_query
out = enrich_query.invoke({'raw_query':'yellow dress for a wedding','gender':'women','occasion':'wedding'}, config={'configurable':{'thread_id':'t'}})
print(out)
"
uvicorn src.main:app --port 8000 &
sleep 3
curl -s -X POST http://localhost:8000/v1/styled-search -H "X-API-Key: $APP_API_KEY" -H "content-type: application/json" -d '{"query":"yellow dress for a wedding"}' | head -c 500
kill %1
```
Expected: `Command` update contains a non-empty `last_semantic_query` and a `current_filters` with `colors` and `category` populated. Legacy endpoint returns its usual JSON.

**Commit:** `feat(agent): wrap enrich_query with state-writes (PRD §Tools, DEC-016)`

---

### Task 3.4 — `search_products` wrapper

**PRD section:** §Tools → `search_products`; §Multi-Turn Refinement (5-result hard cap); DEC-013.

**Files:**
- Modify: `src/agent/tools.py` — append `@tool search_products(semantic_query: str, filters: SearchFilters) -> Command`:
  - `top_k = settings.agent_max_results` — hard-coded; LLM cannot override. PRD invariant.
  - `strict_mode = any(getattr(filters, f) for f in ("colors","occasion","category","gender"))`.
  - Delegates to `src.search.run_search(...)` (unchanged).
  - Returns `Command(update={"messages":[ToolMessage(...)], "last_products": products, "current_filters": filters, "tool_trace": [entry]})`.
  - On failure: empty list, never raises, `entry["error"]` set.

**Deliverable:** returns ≤5 `Product`s for a known-good query; `/v1/search` regression-clean.

**Verification:**
```
python -c "
from src.agent.tools import search_products
from src.agent.schemas import SearchFilters
out = search_products.invoke({'semantic_query':'yellow embroidered saree','filters':SearchFilters(colors=['yellow'], occasion='wedding', gender='women').model_dump()}, config={'configurable':{'thread_id':'t'}})
print(out)
"
uvicorn src.main:app --port 8000 &
sleep 3 && curl -s -X POST http://localhost:8000/v1/search -H "X-API-Key: $APP_API_KEY" -H "content-type: application/json" -d '{"query":"yellow dress"}' | head -c 500 && kill %1
```
Expected: ≤5 products in the update; legacy `/v1/search` returns its usual JSON.

**Commit:** `feat(agent): wrap search_products with 5-result cap (PRD §Tools, DEC-013)`

---

### Task 3.5 — `curate_outfits` wrapper

**PRD section:** §Tools → `curate_outfits`; §Graceful Failure Modes.

**Files:**
- Modify (minimal, DEC-016-compatible): `src/stylist_agent.py` — same optional-kwarg treatment as Task 3.3, only if the prompt is module-level.
- Modify: `src/agent/tools.py` — append `@tool curate_outfits(products: list[Product]) -> Command`:
  - If `products == []`: returns `Command(update={"messages":[ToolMessage(content="[]", ...)], "last_combos": [], "tool_trace": [entry]})` — no fallback combos.
  - Else: calls underlying `src.stylist_agent.curate_outfits(products, system_prompt=get_tool_prompt("stylist_system_prompt"))`.
  - On LLM failure with non-empty input: build fallback combos by zipping top-3 products, `rationale="Stylist unavailable; showing raw results."`, record `entry["error"]`.

**Deliverable:** non-empty input → ≥1 combo with non-empty `rationale`; empty input → `[]`. Legacy `/v1/styled-search` clean.

**Verification:**
```
python -c "
from src.agent.tools import curate_outfits
from src.agent.schemas import Product
ps = [Product(product_id=f'p{i}', image_path='x', score=0.5, category='dress', colors=['red'], occasion='wedding', style_tags=[], caption='c', gender='women') for i in range(3)]
out = curate_outfits.invoke({'products':[p.model_dump() for p in ps]}, config={'configurable':{'thread_id':'t'}})
print(out)
print('---empty---')
print(curate_outfits.invoke({'products':[]}, config={'configurable':{'thread_id':'t'}}))
"
```
Expected: first call yields a Command whose update has `last_combos` with ≥1 combo carrying a non-empty `rationale`; second call yields `last_combos: []` and no fallback combos.

**Commit:** `feat(agent): wrap curate_outfits with rationale guarantee (PRD §Tools)`

---

## Milestone 4 — Graph wiring (DEC-010, DEC-011, DEC-004)

### Task 4.1 — `graph.py` with `create_agent` + HITL + checkpointer + recursion cap

**PRD section:** §Architecture (LangGraph topology); §Safety nets.

**Files:**
- Create: `src/agent/graph.py`:
  - Imports (per LangChain v1 docs — `oss/python/migrate/langchain-v1`; DEC-011 explicitly chose `create_agent` over the deprecated `create_react_agent`):
    - `from langchain.agents import create_agent`
    - `from langchain.agents.middleware import HumanInTheLoopMiddleware`
    - `from langgraph.checkpoint.memory import InMemorySaver`
    - `from langchain_google_genai import ChatGoogleGenerativeAI`
  - Build `llm = ChatGoogleGenerativeAI(model=settings.agent_model_name, google_api_key=settings.gemini_api_key, temperature=0)`.
  - Build `_agent = create_agent(model=llm, tools=[check_required_fields, ask_user, enrich_query, search_products, curate_outfits], system_prompt=get_agent_prompt("agent_system_prompt"), state_schema=FashionAgentState, middleware=[HumanInTheLoopMiddleware(interrupt_on={"ask_user": {"allowed_decisions": ["respond"]}})], checkpointer=InMemorySaver())`.
  - Export `AGENT = _agent.with_config({"recursion_limit": settings.agent_recursion_limit})` — recursion cap travels with every invocation per LangGraph default behavior. Cite docs page on lookup.
  - Module-level singleton so `InMemorySaver` persists across HTTP requests in-process (DEC-004 acknowledged trade-off: lost on restart).

**Deliverable:** graph compiles at import; one happy-path and one interrupt path observable via REPL.

**Verification:**
```
python -c "
from src.agent.graph import AGENT
from langchain_core.messages import HumanMessage
# Happy path — slots inferable from message
out = AGENT.invoke({'messages':[HumanMessage(content='yellow dress for a women wedding')]}, config={'configurable':{'thread_id':'smoke-happy'}})
print('happy keys:', list(out.keys()))
print('combos:', len(out.get('last_combos', [])))
# Interrupt path — slots missing
out2 = AGENT.invoke({'messages':[HumanMessage(content='something nice')]}, config={'configurable':{'thread_id':'smoke-interrupt'}})
print('interrupt path keys:', list(out2.keys()))
print('has __interrupt__:', '__interrupt__' in out2)
"
```
Expected: happy path produces `last_combos` with ≥1 combo; interrupt path includes `__interrupt__` with the consolidated question payload.

**Commit:** `feat(agent): assemble create_agent graph with HITL middleware and checkpointer (PRD §Architecture, DEC-010, DEC-011)`

---

## Milestone 5 — FastAPI surface (PRD §Public APIs)

### Task 5.1 — `POST /v1/chat` (both shapes)

**PRD section:** §Public APIs → `POST /v1/chat`; §Security; §Graceful Failure Modes.

**Files:**
- Create: `src/agent/routes.py`:
  - `router = APIRouter(prefix="/v1/chat", tags=["chat"])`.
  - `POST /` handler: accept a union body. Reject (400) if both `message` and `resume` are present, or neither. Reject (400) if `len(message) > 500`.
  - Shape 1 (`message`): `result = AGENT.invoke({"messages":[HumanMessage(content=req.message)]}, config={"configurable":{"thread_id": req.thread_id}})`.
  - Shape 2 (`resume`): `from langgraph.types import Command; result = AGENT.invoke(Command(resume={"decisions": [d.model_dump() for d in req.resume.decisions]}), config={"configurable":{"thread_id": req.thread_id}})` (LangChain docs `oss/python/langchain/human-in-the-loop.mdx` + `oss/python/langgraph/interrupts.mdx`).
  - Response build:
    - If `result.get("__interrupt__")`: return `ChatInterruptResponse` with `pending_action.name="ask_user"`, `arguments.question = <extracted from interrupt payload>`.
    - Else: read graph state via `state = AGENT.get_state(config={"configurable":{"thread_id": req.thread_id}})`; build `ChatFinalResponse` from `state.values["last_combos"]`, `gathered_slots`, `current_filters`, `tool_trace`.
  - Always include fresh `request_id` (UUID), `turn_count` (read from state), `latency_ms` (measured around invoke).
  - Catch `GraphRecursionError` → return 500 `{"error": "Agent took too many steps. Please start a new thread."}` per PRD §Graceful Failure Modes.
- Modify: `src/main.py` — `from src.agent.routes import router as chat_router; app.include_router(chat_router)`. Confirm existing `X-API-Key` middleware covers `/v1/chat` (it covers everything except `/v1/health`).

**Deliverable:** Swagger `/docs` exposes `POST /v1/chat`; all six scenarios below pass.

**Verification (Swagger walk-through — paste the JSON responses inline in the commit description):**
1. POST `{"thread_id":"t1","message":"yellow dress for a women wedding"}` → `type:"final"`, combos non-empty.
2. POST `{"thread_id":"t2","message":"something nice"}` → `type:"interrupt"`, `pending_action.arguments.question` mentions both gender and occasion.
3. POST `{"thread_id":"t2","resume":{"decisions":[{"type":"respond","message":"women wedding"}]}}` → `type:"final"`.
4. POST with both `message` and `resume` → 400.
5. POST with neither → 400.
6. POST with `message` of 501 chars → 400.

**Commit:** `feat(api): add /v1/chat with new + resume shapes (PRD §Public APIs)`

---

### Task 5.2 — `GET /v1/chat/threads/{thread_id}` diagnostic

**PRD section:** §Public APIs → `GET /v1/chat/threads/{thread_id}`.

**Files:**
- Modify: `src/agent/routes.py` — add `GET /threads/{thread_id}`:
  - `state = AGENT.get_state(config={"configurable":{"thread_id": thread_id}})`; if `state is None or not state.values`: 404.
  - Build response: `messages` (role + content only, no tool internals), `pending_action` (non-null if `state.tasks` contains an interrupt — extract per the interrupts docs), `created_at` / `last_activity_at` from state metadata if available; otherwise omit.

**Deliverable:** Swagger shows the diagnostic; round-trip works.

**Verification:** after Task 5.1 scenarios 1–3, run via Swagger:
- GET `/v1/chat/threads/t1` → returns the messages and `pending_action: null`.
- GET `/v1/chat/threads/t2` → returns messages and `pending_action: null` (interrupt was resolved).
- GET `/v1/chat/threads/does-not-exist` → 404.

**Commit:** `feat(api): add /v1/chat/threads/{id} diagnostic (PRD §Public APIs)`

---

## Milestone 6 — Frontend ChatPanel (DEC-008)

### Task 6.1 — Chat API client + state hook

**PRD section:** §Frontend Changes.

**Files:**
- Create: `frontend/src/chat/chatApi.js`:
  - `sendMessage(threadId, text)` — POST `/v1/chat` shape 1.
  - `sendResume(threadId, replyText)` — POST `/v1/chat` shape 2 with `decisions=[{type:"respond", message: replyText}]`.
  - `getThread(threadId)` — GET `/v1/chat/threads/{threadId}`.
  - All wrap the same `fetch` helper as `frontend/src/api.js` so `X-API-Key` propagation is identical.
- Create: `frontend/src/chat/chatState.js`:
  - Custom hook `useChatState()` exposing `{ threadId, messages, pendingInterrupt, lastCombos, send, resume, reset }`.
  - `threadId` is a client-generated UUID, regenerated on `reset()`.
  - `send(text)` posts shape 1 and merges the response; `resume(text)` posts shape 2 and merges; both update `pendingInterrupt` and `lastCombos` from the response.

**Deliverable:** the two modules import cleanly into a temporary scratch component.

**Verification:**
- `cd frontend && npm run build` → exits 0.
- Add a temporary `<button onClick={() => chatApi.sendMessage('smoke-1', 'yellow dress for a women wedding').then(r => console.log(r))}>` in `App.jsx`, run `npm run dev`, click it, paste browser-console output into the commit description, then revert the scratch button before commit.

**Commit:** `feat(frontend): add chat API client and useChatState hook (PRD §Frontend, DEC-008)`

---

### Task 6.2 — `ChatPanel` + `InterruptCard`

**PRD section:** §Frontend Changes.

**Files:**
- Create: `frontend/src/chat/ChatPanel.jsx` + `ChatPanel.css`:
  - Side-rail panel docked into the existing search screen (NOT a new route — DEC-008).
  - Message list with user/assistant bubbles; system bubble style for cap-fallback notice.
  - Input + send button → `chatState.send`.
  - When `pendingInterrupt` is non-null, render `<InterruptCard />` instead of the input.
  - When `lastCombos` arrives in a `final` response, render each combo inline in the chat as a mini-card (image + category + bold `rationale`). Do not reuse the existing `ResultsGrid` — keeps chat self-contained.
- Create: `frontend/src/chat/InterruptCard.jsx`:
  - Renders `pendingInterrupt.arguments.question` prominently.
  - Has its own reply input + submit → `chatState.resume`.
- Modify: `frontend/src/App.jsx` — embed `<ChatPanel />` as a right-side panel in the existing layout. Do NOT modify `SearchBar`, `ResultsGrid`, or `ProductCard`.

**Deliverable:** chat panel renders alongside the legacy search; both work independently.

**Verification (browser walk-through, paste a screenshot or text trace into the commit description):**
- `cd frontend && npm run dev`, open the app.
- In ChatPanel: type "yellow dress for a women wedding" → combos with rationales appear.
- Click reset, type "something nice" → InterruptCard appears with the consolidated question; reply "women wedding" → combos appear.
- Top-of-screen legacy search bar: run a search → existing `ResultsGrid` populates (regression).
- `npm run build` exits 0.

**Commit:** `feat(frontend): add ChatPanel and InterruptCard (PRD §Frontend, DEC-008)`

---

## Milestone 7 — Manual E2E validation (PRD §Testing Strategy)

### Task 7.1 — Walk all 17 acceptance scenarios

**PRD section:** §Testing Strategy → scenarios 1–17.

**Procedure:** server + dev frontend both running. For each scenario, write a pass/fail line in a temporary `specs/_v3.0-acceptance-run.md` (gitignored — paste into the final PR description on completion, then delete).

**Scenarios (numbered per PRD):**
- **Single-turn (1–7):** happy path, consolidated single ask, cap fallback after 3 asks, no results, concurrent threads, server restart, invalid request shapes.
- **Multi-turn (8–14):** variant add-color, variant change-occasion, pagination denial, pagination synonyms, zero-result variant, turn-count cap at 21, mixed "more like these but in red".
- **Observability (15–17):** `tool_trace` populated, unique `request_id` per request, forced `curate_outfits` failure yields fallback combos + non-null `error` in trace.

**Deliverable:** all 17 pass. If any fail, file a single-task fix commit for each, then re-run that scenario.

**Verification (per PRD §Testing Strategy):** record actual JSON snippets or screenshots for each scenario as the evidence. Per `verification-before-completion`, "all tests pass" must be backed by the actual run output, not extrapolation.

**Commits:** none required if all green. One `fix(agent): <scenario>` commit per failure.

---

## Final verification checklist (run before declaring v3.0 done)

- [ ] `git diff main..HEAD --stat -- src/ ':!src/agent/'` shows only `src/config.py`, `src/main.py`, and (if strictly needed) the optional-kwarg additions to `src/query_enrichment.py` / `src/stylist_agent.py` from Tasks 3.3 / 3.5 — DEC-016 invariant.
- [ ] `/v1/search` and `/v1/styled-search` responses match baseline captured at HEAD before Task 1.1 — DEC-007 additive guarantee.
- [ ] All 17 acceptance scenarios passed in Task 7.1.
- [ ] `prompts/*.yaml` loads cleanly; no Python file embeds an LLM prompt (`rg -n 'You are' src/` returns no prompt-shaped strings).
- [ ] Hard caps verified: `recursion_limit=10` (scenario 3 + manual), `MAX_ASK_USER=3` (scenario 3), `MAX_RESULTS=5` (scenarios 1 + 8), `MAX_TURNS=20` (scenario 13).
- [ ] `graphify update .` run — per CLAUDE.md.
- [ ] `/ultrareview` clean on the branch.
- [ ] `/security-review` clean (focus areas: prompt injection on `/v1/chat`, tool-arg validation, secret handling, thread-id isolation across concurrent threads).
- [ ] `learnings/design-decisions-log.md` carries DEC-017 (ordering rationale).
- [ ] `learnings/project-build-journal.md` updated with any non-obvious gotchas discovered.
- [ ] `.claude-session-log.md` updated with the v3.0 ship-it entry.
- [ ] Run `superpowers:finishing-a-development-branch` to choose merge strategy.

---

## Out of scope (explicit, deferred per PRD §Non-Goals)

LangSmith tracing, `structlog`, Guardrails-AI / NeMo input/output rails, eval harness, pagination / "more options" UI, combo-swap refinement, `SummarizationMiddleware`, per-user rate limiting, SSE streaming, Docker / deployment, `AsyncPostgresSaver`, removing `src/static/`, multi-agent supervisor migration. Each lands as its own v3.1+ PRD.
