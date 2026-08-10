# Multi-Provider LLM Failover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add automatic OpenAI failover behind the existing `src/llm_gateway/` facade so text tasks and the agent keep working when Vertex/Gemini fails.

**Architecture:** Two engines inside the gateway, public API unchanged. Text tasks (`generate_text`) go through a LiteLLM `Router` (Vertex-primary → OpenAI-fallback, per-request fallback + cooldown). The agent (`get_chat_model`) gets a LangChain `ChatGoogleGenerativeAI.with_fallbacks([ChatOpenAI])` chain (per-request failover, native tool-calling). Cost tracking + LangSmith wiring register once at startup.

**Tech Stack:** Python 3.11, FastAPI, pydantic-settings, LiteLLM (`Router`), LangChain (`langchain-google-genai`, `langchain-openai`), Google Vertex AI via ADC, OpenAI.

## Global Constraints

- **No unit/integration test files.** Verify manually — `python -c` smoke checks and Swagger/curl. (CLAUDE.md §9)
- **No new DB, task queue, framework, or infra** beyond `langchain-openai` (required for the approved agent-fallback path). (CLAUDE.md §9)
- **No wrapper/shim/adapter classes** to work around SDK gaps — use native mechanisms only. (DEC-023)
- **Prefer functions/modules over classes.** No ABCs or factory patterns. (CLAUDE.md §8)
- **Secrets via `.env` + pydantic-settings only.** Reuse existing `openai_api_key`. No hardcoded keys.
- **Type hints on all signatures. `snake_case` funcs, `PascalCase` models, `UPPER_SNAKE_CASE` consts.**
- **Public gateway API stays identical:** `generate_text(*, task, model, system_prompt, user_message, temperature=None) -> str`, `get_chat_model(*, task, model, temperature=0)`, `LLMGatewayError`. Callers are NOT modified.
- After code changes run `graphify update .` (AST-only, no API cost). (CLAUDE.md §3)
- One task → one commit, referencing the task. Branch: `feat/multi-provider-failover` (already created).

---

### Task 1: Config — failover settings + dormant tier settings

**Files:**
- Modify: `src/config.py` (Settings class, after `image_generation_model_name` / `llm_backend` block)

**Interfaces:**
- Produces: `Settings.llm_primary_model: str`, `Settings.llm_fallback_model: str`, `Settings.llm_fallback_enabled: bool`, `Settings.llm_cooldown_seconds: int`, `Settings.llm_allowed_fails: int`. Existing `openai_api_key`, `google_cloud_project`, `google_cloud_location` reused.

- [x] **Step 1: Add settings + mark dormant ones**

In `src/config.py`, inside `class Settings`, add:

```python
    # --- Multi-provider failover (2026-07-13 design) ---
    # Single Vertex HIGH model used for ALL text tasks + the agent (Router prepends vertex_ai/).
    llm_primary_model: str = "gemini-2.5-pro"
    # Single OpenAI failover model for ALL tasks. MUST support tool-calling (agent uses it too).
    # No safe default — set LLM_FALLBACK_MODEL in .env (e.g. a GPT-4-class tool-calling model).
    llm_fallback_model: str = ""
    # Master switch. False => Vertex-only (pre-failover behavior).
    llm_fallback_enabled: bool = True
    # LiteLLM Router cooldown: park a deployment for N seconds after allowed_fails failures.
    llm_cooldown_seconds: int = 60
    llm_allowed_fails: int = 3
```

Then above the existing per-task model settings (`search_enrichment_model_name`,
`stylist_model_name`, `image_generation_model_name`, `agent_model_name`,
`litellm_test_model_name`) add a single comment line:

```python
    # NOTE: per-task model names below are RESERVED for future per-task/tier routing.
    # Currently DORMANT — all text tasks + the agent use llm_primary_model (see llm_gateway).
```

Leave `llm_backend` as-is but append to its comment: `# superseded for text by the Router; retained.`

- [x] **Step 2: Smoke-check the settings load**

Run:
```bash
venv/bin/python -c "from src.config import get_settings; s=get_settings(); print(s.llm_primary_model, s.llm_fallback_enabled, s.llm_allowed_fails, s.llm_cooldown_seconds, repr(s.llm_fallback_model))"
```
Expected: `gemini-2.5-pro True 3 60 ''` (fallback model empty until set in `.env`).

- [x] **Step 3: Commit**

```bash
git add src/config.py
git commit -m "feat(llm): add multi-provider failover settings; mark per-task models dormant"
```

---

### Task 2: Callbacks — cost tracking + LangSmith registration

**Files:**
- Create: `src/llm_gateway/callbacks.py`

**Interfaces:**
- Produces: `register_llm_callbacks() -> None` — idempotent; registers a cost-logging success callback and (if LangSmith env is present) the LiteLLM `"langsmith"` integration.

- [x] **Step 1: Create the callbacks module**

Create `src/llm_gateway/callbacks.py`:

```python
"""LiteLLM observability: per-call cost logging + LangSmith wiring.

Registered once at gateway init. Cost is logged via the stdlib logging module
(no logging framework, per CLAUDE.md). LangSmith is opt-in: only wired when the
existing LANGCHAIN_TRACING_V2/LANGCHAIN_API_KEY env is present.
"""

from __future__ import annotations

import logging
import os

import litellm

logger = logging.getLogger(__name__)

_REGISTERED = False


def _log_cost(kwargs: dict, completion_response, start_time, end_time) -> None:
    """LiteLLM success callback: log model, tokens, and USD cost for one call."""
    try:
        cost = kwargs.get("response_cost")
        if cost is None:
            cost = litellm.completion_cost(completion_response=completion_response)
        model = kwargs.get("model")
        usage = getattr(completion_response, "usage", None)
        logger.info("llm_cost — model=%s cost_usd=%.6f usage=%s", model, cost or 0.0, usage)
    except Exception as exc:  # cost logging must never break a request
        logger.debug("llm_cost logging skipped: %s", type(exc).__name__)


def register_llm_callbacks() -> None:
    """Idempotently register cost + LangSmith callbacks on the litellm module."""
    global _REGISTERED
    if _REGISTERED:
        return
    callbacks: list = [_log_cost]
    if os.environ.get("LANGCHAIN_TRACING_V2", "").lower() == "true" and os.environ.get(
        "LANGCHAIN_API_KEY"
    ):
        callbacks.append("langsmith")
        logger.info("llm_gateway: LangSmith callback enabled for LiteLLM calls")
    litellm.success_callback = callbacks
    _REGISTERED = True
    logger.info("llm_gateway: cost tracking callback registered")
```

- [x] **Step 2: Smoke-check registration**

Run:
```bash
venv/bin/python -c "from src.llm_gateway.callbacks import register_llm_callbacks; import litellm; register_llm_callbacks(); print([c if isinstance(c,str) else c.__name__ for c in litellm.success_callback])"
```
Expected: prints `['_log_cost']` (or `['_log_cost', 'langsmith']` if LangSmith env is set). No exception.

- [x] **Step 3: Commit**

```bash
git add src/llm_gateway/callbacks.py
git commit -m "feat(llm): add LiteLLM cost-tracking + LangSmith callback registration"
```

---

### Task 3: Providers — Router builder + chat-model builder

**Files:**
- Modify (rewrite): `src/llm_gateway/providers.py`
- Modify: `requirements.txt` (add `langchain-openai`)

**Interfaces:**
- Consumes: `Settings` (Task 1 fields).
- Produces: `build_text_router(settings: Settings) -> litellm.Router` with model group `"vertex-high"` and fallback `"openai-fallback"`; `build_chat_model(settings: Settings)` returning a LangChain `Runnable`/`BaseChatModel` (Vertex, optionally `.with_fallbacks([ChatOpenAI])`).

- [x] **Step 1: Add the langchain-openai dependency**

In `requirements.txt` add on its own line:
```
langchain-openai
```
Install:
```bash
venv/bin/pip install langchain-openai
```
Expected: installs successfully (pulls a langchain-openai compatible with the pinned langchain).

- [x] **Step 2: Rewrite providers.py as builder functions**

Replace the entire contents of `src/llm_gateway/providers.py` with:

```python
"""Provider construction for the LLM gateway.

Two builders — one per engine:
  * build_text_router  -> LiteLLM Router (Vertex primary, OpenAI fallback, cooldown)
  * build_chat_model   -> LangChain chat model (Vertex) with OpenAI fallback for the agent

Functions, not strategy classes (CLAUDE.md §8). No shims (DEC-023): both use the
providers' native mechanisms (LiteLLM Router fallbacks; LangChain with_fallbacks).
"""

from __future__ import annotations

from src.config import Settings

# Router group names (used by gateway.generate_text).
PRIMARY_GROUP = "vertex-high"
FALLBACK_GROUP = "openai-fallback"


def build_text_router(settings: Settings):
    """Build a LiteLLM Router: Vertex-high primary, OpenAI fallback, per-request + cooldown."""
    from litellm import Router

    model_list = [
        {
            "model_name": PRIMARY_GROUP,
            "litellm_params": {
                "model": f"vertex_ai/{settings.llm_primary_model}",
                "vertex_project": settings.google_cloud_project,
                "vertex_location": settings.google_cloud_location,
            },
        }
    ]
    fallbacks: list = []
    if settings.llm_fallback_enabled and settings.llm_fallback_model:
        model_list.append(
            {
                "model_name": FALLBACK_GROUP,
                "litellm_params": {
                    "model": f"openai/{settings.llm_fallback_model}",
                    "api_key": settings.openai_api_key,
                },
            }
        )
        fallbacks = [{PRIMARY_GROUP: [FALLBACK_GROUP]}]

    return Router(
        model_list=model_list,
        fallbacks=fallbacks,
        allowed_fails=settings.llm_allowed_fails,
        cooldown_time=settings.llm_cooldown_seconds,
        num_retries=3,
    )


def build_chat_model(settings: Settings, *, temperature: float = 0):
    """Build the agent chat model: Vertex primary with a native OpenAI fallback chain."""
    from langchain_google_genai import ChatGoogleGenerativeAI

    base = ChatGoogleGenerativeAI(
        model=settings.llm_primary_model,
        vertexai=settings.google_genai_use_vertexai,
        project=settings.google_cloud_project,
        location=settings.google_cloud_location,
        temperature=temperature,
    )
    if not settings.llm_fallback_enabled or not settings.llm_fallback_model:
        return base

    from langchain_openai import ChatOpenAI

    fallback = ChatOpenAI(
        model=settings.llm_fallback_model,
        api_key=settings.openai_api_key,
        temperature=temperature,
    )
    return base.with_fallbacks([fallback])
```

- [x] **Step 3: Smoke-check the builders (no network calls)**

Run:
```bash
venv/bin/python -c "from src.config import get_settings; from src.llm_gateway.providers import build_text_router, build_chat_model; s=get_settings(); r=build_text_router(s); print('router_groups=', sorted({m['model_name'] for m in r.model_list})); print('chat_type=', type(build_chat_model(s)).__name__)"
```
Expected: with no `LLM_FALLBACK_MODEL` set → `router_groups= ['vertex-high']` and `chat_type= ChatGoogleGenerativeAI`. With `LLM_FALLBACK_MODEL=gpt-5.6-terra` set → `router_groups= ['openai-fallback', 'vertex-high']` and `chat_type= RunnableWithFallbacks`. Constructing must not make network calls.

- [x] **Step 4: Commit**

```bash
git add requirements.txt src/llm_gateway/providers.py
git commit -m "feat(llm): Router + chat-model builders with OpenAI fallback (replaces provider strategies)"
```

---

### Task 4: Gateway wiring — route text through Router, agent through fallback chain

**Files:**
- Modify (rewrite): `src/llm_gateway/gateway.py`
- Verify unchanged: `src/llm_gateway/__init__.py` (still exports `generate_text`, `get_chat_model`, `LLMGatewayError`)

**Interfaces:**
- Consumes: `build_text_router`, `build_chat_model`, `PRIMARY_GROUP` (Task 3); `register_llm_callbacks` (Task 2); `Settings` (Task 1).
- Produces: unchanged public API `generate_text(...) -> str`, `get_chat_model(...)`, `LLMGatewayError`.

- [x] **Step 1: Rewrite gateway.py**

Replace the entire contents of `src/llm_gateway/gateway.py` with:

```python
"""LLM gateway facade — single entry point for LLM connectivity.

Text tasks use a LiteLLM Router (Vertex primary, OpenAI fallback, cooldown).
The agent uses a LangChain chat model with a native OpenAI fallback chain.
Callers stay provider-agnostic and pass a task label; the `model` argument is
currently DORMANT (all tasks resolve to the single primary group) — kept so
re-enabling per-task tiers later is a config change, not a caller change.
"""

from __future__ import annotations

import logging
import time

from src.config import get_settings
from src.llm_gateway.callbacks import register_llm_callbacks
from src.llm_gateway.providers import PRIMARY_GROUP, build_chat_model, build_text_router

logger = logging.getLogger(__name__)

_router = None


class LLMGatewayError(RuntimeError):
    """Raised when all LLM attempts (primary + fallback) fail.

    Subclasses RuntimeError so existing callers that catch RuntimeError keep working.
    """


def _get_router():
    """Lazily build + cache the text Router, registering observability callbacks once."""
    global _router
    if _router is None:
        register_llm_callbacks()
        _router = build_text_router(get_settings())
    return _router


def generate_text(
    *,
    task: str,
    model: str,
    system_prompt: str,
    user_message: str,
    temperature: float | None = None,
) -> str:
    """Generate text via the Router (primary + fallback + cooldown owned by LiteLLM).

    `task` is a caller label for logging. `model` is currently dormant (routed to the
    single primary group). Raises LLMGatewayError if primary AND fallback both fail.
    """
    router = _get_router()
    start = time.monotonic()
    kwargs: dict = {
        "model": PRIMARY_GROUP,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    }
    if temperature is not None:
        kwargs["temperature"] = temperature

    try:
        response = router.completion(**kwargs)
    except Exception as exc:  # provider-agnostic: Router already retried + failed over
        raise LLMGatewayError(f"LLM call failed (task={task}): {exc}") from exc

    latency_ms = int((time.monotonic() - start) * 1000)
    used_model = getattr(response, "model", "?")
    logger.info("llm_gateway ok — task=%s model=%s latency_ms=%d", task, used_model, latency_ms)
    return response.choices[0].message.content


def get_chat_model(*, task: str, model: str, temperature: float = 0):
    """Return the agent chat model (Vertex primary + native OpenAI fallback chain).

    `model` is dormant (uses settings.llm_primary_model). Tool-calling is native on
    both providers. Fallback is per-request (no cooldown) — an accepted trade-off.
    """
    logger.info("llm_gateway chat model — task=%s (primary + fallback chain)", task)
    return build_chat_model(get_settings(), temperature=temperature)
```

- [x] **Step 2: Confirm the package still imports and exports are intact**

Run:
```bash
venv/bin/python -c "import src.llm_gateway as g; print(sorted(g.__all__)); print(callable(g.generate_text), callable(g.get_chat_model), issubclass(g.LLMGatewayError, RuntimeError))"
```
Expected: `['LLMGatewayError', 'generate_text', 'get_chat_model']` then `True True True`.

- [x] **Step 3: Confirm the agent graph still builds (imports get_chat_model at module load)**

Run:
```bash
venv/bin/python -c "import src.agent.graph as gr; print('agent graph import OK')"
```
Expected: `agent graph import OK` (this exercises `get_chat_model(task='agent', ...)` at import; requires ADC creds present, as today).

- [x] **Step 4: Update the knowledge graph**

```bash
graphify update .
```
Expected: completes (AST-only, no API cost).

- [x] **Step 5: Commit**

```bash
git add src/llm_gateway/gateway.py graphify-out
git commit -m "feat(llm): route text via Router + agent via fallback chain; drop manual retry loop"
```

---

### Task 5: Document config in `.env.example`

**Files:**
- Modify: `.env.example`

- [x] **Step 1: Add the new vars**

In `.env.example`, under the OpenAI section (or a new `# LLM failover` block), add:

```bash
# LLM failover (Vertex primary -> OpenAI fallback)
LLM_PRIMARY_MODEL=gemini-2.5-pro
# OpenAI failover model — must support tool-calling (agent uses it on failover).
# gpt-5.6-terra = balanced intelligence/cost (chosen). Alternatives: gpt-5.6 (sol, frontier), gpt-5.6-luna (cheap).
LLM_FALLBACK_MODEL=gpt-5.6-terra
LLM_FALLBACK_ENABLED=true
LLM_COOLDOWN_SECONDS=60
LLM_ALLOWED_FAILS=3
```

- [x] **Step 2: Commit**

```bash
git add .env.example
git commit -m "docs(env): document LLM failover settings"
```

---

### Task 6: End-to-end failover verification (manual — no code)

**Files:** none (verification only). Uses a running server on port 8083 and a real `.env` with `OPENAI_API_KEY` + `LLM_FALLBACK_MODEL` set.

- [x] **Step 1: Happy path (Vertex primary)**

Start the server: `PORT=8083 venv/bin/uvicorn src.main:app --port 8083 --reload`.
Call `POST /v1/search/styled` (Swagger UI) with a normal query. Expected: 200 with enriched results. Server log shows `llm_gateway ok` and an `llm_cost` line.

- [x] **Step 2: Text failover**

Stop server. Set `LLM_PRIMARY_MODEL=bogus-model-xyz` in `.env`. Restart. Repeat the styled-search call.
Expected: still 200 with results — served by OpenAI. Log shows a Router fallback and `used_model` is the OpenAI model. Confirms per-request fallback for text.

- [x] **Step 3: Agent failover**

With the bogus primary still set, call `POST /v1/chat` with `{"message":"casual suit for men"}`.
Expected: completes a tool-calling run (enrich → search → curate) via OpenAI; response `type:final` with combos. Confirms the LangChain fallback chain preserves tool-calling.

- [x] **Step 4: Both-fail graceful degradation**

Also set `LLM_FALLBACK_MODEL=bogus-openai-xyz`. Restart. Repeat styled search.
Expected: no crash — enrichment degrades to the raw query (per existing caller handling); stylist returns fallback combos. HTTP still 200.

- [x] **Step 5: Kill switch**

Restore real models. Set `LLM_FALLBACK_ENABLED=false`. Restart. Confirm normal operation and that the Router has no fallback group (Vertex-only). Then restore `.env` to real values + `true`.

- [x] **Step 6: Record results in the session log**

Append a dated entry to `.claude-session-log.md` (gitignored) summarizing which of steps 1–5 passed and any surprises.

---

## Notes for the implementer

- **LiteLLM callback API varies by version.** If `litellm.success_callback` rejects a mixed list of a callable + `"langsmith"` on the installed version, register the callable via `litellm.callbacks = [...]` (CustomLogger path) instead and keep `success_callback = ["langsmith"]`. The Step-2 smoke check in Task 2 will surface a mismatch immediately.
- **`response.model`** on a Router completion reflects the deployment actually used — that's how Steps 2–3 of Task 6 confirm which provider served the call.
- **ADC required** for any step that actually calls Vertex (import of `src.agent.graph`, and all of Task 6). Offline smoke checks (Tasks 1–4) only construct objects and must not hit the network.
