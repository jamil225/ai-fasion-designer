# Design: Multi-Provider LLM Failover (Vertex → OpenAI)

**Date:** 2026-07-13
**Status:** Approved (design) — pending implementation plan
**Branch:** `agentic-implementation` (default)
**Related:** builds on `src/llm_gateway/` (commit `19fa54f`), DEC-023 (no shims — upgrade/use native), the LiteLLM sandbox endpoint (`d6638b1`)

---

## 1. Problem & Goals

The application currently routes all text LLM calls through the `src/llm_gateway/` facade, which
talks to **Vertex AI (Gemini)** via ADC. There is **no provider-level backup**: if Vertex is
degraded or failing, every LLM-backed feature (query enrichment, stylist, and the agent) fails.

**Goal:** add **OpenAI as an automatic failover** so that when Vertex fails, calls continue on
OpenAI. Do this the enterprise-grade way — reuse LiteLLM's native resilience rather than
hand-rolling — and keep the caller-facing gateway API unchanged.

### In scope
- Vertex-primary → OpenAI-failover for **text tasks** (LiteLLM Router: per-request fallback + cooldown).
- Vertex-primary → OpenAI-failover for the **agent** (LangChain-native fallback chain, tool-calling preserved).
- Two operational extras the app should have: **cost/token tracking** and **LangSmith wiring** for LiteLLM calls.

### Out of scope (deferred, deliberately)
- **Per-task capability tiers** (high/mid/low × provider). The *config scaffolding is kept dormant*
  (see §3) so this can return later as a config change, not a rewrite.
- **LiteLLM Proxy server** (virtual keys, team budgets, SSO, central gateway). Staying on the
  in-process SDK `Router`. Proxy is the future escalation path when multiple apps/teams need a
  shared governed endpoint.
- Redis / semantic caching (would add infra — needs explicit approval per CLAUDE.md).
- Image generation (virtual try-on) — it is a Gemini native-image model, not a text tier; untouched.

---

## 2. Simplification decisions (locked with user)

- **Primary (Vertex):** a **single HIGH model for all text tasks and the agent** now.
  Consequence: query-enrichment moves off `gemini-2.5-flash` onto the HIGH model — slightly more
  cost/latency on that high-volume call, accepted for simplicity.
- **Failover (OpenAI):** a **single OpenAI model for all tasks**. No per-task differentiation on the
  fallback side.
- **Tier config preserved but dormant:** existing per-task model settings stay in `config.py`,
  unused, marked reserved.
- **Failover behavior:** per-request fallback **+ cooldown** for text (LiteLLM Router option C);
  per-request fallback **only** (no cooldown) for the agent — accepted caveat.

---

## 3. Architecture

Public surface of `src/llm_gateway/` is **unchanged**. Callers (`query_enrichment.py`,
`stylist_agent.py`, `agent/graph.py`) are not modified. Two engines live inside the gateway:

```
                 ┌─────────────────────────── src/llm_gateway/ ───────────────────────────┐
 callers ──▶ generate_text(...) ─────▶ LiteLLM Router  ─▶ vertex-high ──(fail)──▶ openai-fallback
            (enrich, stylist)          (retry+fallback+cooldown, cost+langsmith callbacks)
                                                                                            
 graph ───▶ get_chat_model(...) ─────▶ ChatGoogleGenerativeAI(vertex, HIGH)
                                          .with_fallbacks([ChatOpenAI(fallback)])
                                          (per-request failover, native tool-calling)
            └────────────────────────────────────────────────────────────────────────────┘
```

Rationale for two engines: `generate_text` only needs a string, so the Router (which returns
completions) fits and gives the full resilience package. The agent needs a LangChain `BaseChatModel`
with tool-calling + streaming, which the Router does not hand back; LangChain's native
`.with_fallbacks()` over `ChatGoogleGenerativeAI` and `ChatOpenAI` is the supported, shim-free way
to get failover there. Both engines resolve their models from the *same* config values, so there is
one place to change models.

---

## 4. Configuration (`src/config.py`)

New settings (safe defaults; secrets via env only):

| Setting | Default | Purpose |
|---|---|---|
| `llm_primary_model` | `gemini-2.5-pro` | Single Vertex HIGH model (bare name; Router prepends `vertex_ai/`). |
| `llm_fallback_model` | *(empty — must be set)* | Single OpenAI failover model id. **Must support tool-calling** (used by the agent too). "5.5/5.4" are not valid OpenAI ids — fill the real one. |
| `llm_fallback_enabled` | `True` | Master switch. `False` → Vertex-only, today's behavior. |
| `llm_cooldown_seconds` | `60` | Router cooldown window for a failing deployment. |
| `llm_allowed_fails` | `3` | Failures within the window before a deployment is cooled down. |

Reused (already present): `openai_api_key` (currently embeddings), `google_cloud_project`,
`google_cloud_location`.

**Kept dormant** (commented `# reserved for future per-task/tier routing`): `agent_model_name`,
`stylist_model_name`, `search_enrichment_model_name`, `image_generation_model_name`,
`litellm_test_model_name`. The `llm_backend` setting is superseded for the text path by the Router;
it is retained but no longer selects the text provider (documented).

---

## 5. Text path — `generate_text`

Build a **single Router** at gateway import time:

```
model_list = [
  {"model_name": "vertex-high",     "litellm_params": {"model": "vertex_ai/<primary>",
                                                        "vertex_project": ..., "vertex_location": ...}},
  {"model_name": "openai-fallback", "litellm_params": {"model": "openai/<fallback>",
                                                        "api_key": <openai_api_key>}},
]
Router(model_list=model_list,
       fallbacks=[{"vertex-high": ["openai-fallback"]}] if llm_fallback_enabled else [],
       allowed_fails=llm_allowed_fails,
       cooldown_time=llm_cooldown_seconds,
       num_retries=MAX_RETRIES)
```

`generate_text` calls `router.completion(model="vertex-high", messages=[system, user], temperature=...)`.

- The Router now owns **retry + fallback + cooldown**, so the **hand-rolled retry loop in
  `gateway.py` is removed for the text path** (replaced by Router config — cleaner, DEC-023-clean).
- The `model` argument callers pass becomes **dormant**: all text tasks resolve to the single
  `vertex-high` group. Signatures stay unchanged so re-enabling tiers later is a config/routing
  change, not a caller change.
- On total failure (both providers) the Router raises; the gateway wraps it as the existing
  `LLMGatewayError` (a `RuntimeError`), which callers already catch and degrade on
  (enrichment → raw query; stylist → fallback combos).

---

## 6. Agent path — `get_chat_model`

```
base = ChatGoogleGenerativeAI(model=<primary>, vertexai=True, project=..., location=..., temperature=0)
if llm_fallback_enabled:
    return base.with_fallbacks([ChatOpenAI(model=<fallback>, api_key=<openai_api_key>, temperature=0)])
return base
```

- Per-request failover; **no cooldown** (accepted caveat — the agent path can't cheaply share the
  Router's cooldown state).
- Both models have native, well-tested **tool-calling**, which is *more* reliable for the ReAct
  agent than the previously-pinned `ChatLiteLLM`+Vertex path.
- `create_react_agent` consumes the returned runnable unchanged.

---

## 7. Observability & cost

- **LangSmith:** add `"langsmith"` to `litellm.success_callback` so Router (text) calls appear in
  the **existing** LangSmith project next to the agent traces (LangChain already instruments the
  agent). Uses the LangSmith env already configured at startup — no new wiring beyond the callback
  registration.
- **Cost tracking:** register a LiteLLM success callback that logs `model`, token counts, and
  LiteLLM's computed `response_cost` per call through the built-in `logging` module (no new
  framework, per CLAUDE.md). Agent-side cost already surfaces via LangSmith.

Both are registered once at gateway/startup init, guarded so a missing LangSmith key is a no-op
(consistent with today's optional-tracing behavior).

---

## 8. Error handling summary

| Scenario | Behavior |
|---|---|
| Vertex transient failure (text) | Router retries, then fails over to OpenAI for that call. |
| Vertex failing repeatedly (text) | Router cools Vertex down for `llm_cooldown_seconds`; traffic goes to OpenAI; then re-probes. |
| Both providers fail (text) | `LLMGatewayError` → caller graceful degradation (unchanged). |
| Vertex failure (agent) | `with_fallbacks` routes that request to OpenAI; agent still tool-calls. |
| Both fail (agent) | Propagates as today. |
| `llm_fallback_enabled=False` | Vertex-only, current behavior — clean kill switch. |

---

## 9. Verification (manual — no unit tests per CLAUDE.md)

Drive via Swagger UI / chat panel and the `/verify` flow:

1. **Happy path:** styled search + chat succeed on Vertex HIGH model.
2. **Text failover:** set `llm_primary_model` to a bogus value → confirm enrichment/stylist still
   return results (served by OpenAI), and logs show the fallback.
3. **Agent failover:** same bogus primary → confirm `/v1/chat` still completes a tool-calling run
   via OpenAI.
4. **Observability:** confirm cost + token log lines appear and Router calls show in LangSmith.
5. **Both-fail degradation:** bogus primary + bogus fallback → confirm graceful degradation
   (raw query / fallback combos), no crash.
6. **Kill switch:** `llm_fallback_enabled=False` → Vertex-only, no OpenAI attempts.

---

## 10. Future work (explicitly deferred)

- Re-activate per-task **capability tiers** (high/mid/low) using LiteLLM Router **model groups** —
  the dormant config from §4 becomes multiple Router groups; callers pass a tier. No caller changes.
- Cooldown for the agent path (would need shared health state between the Router and the LangChain
  chat model).
- LiteLLM Proxy server if/when multiple apps or teams need one governed LLM endpoint.
- Response caching (in-memory first; Redis only with explicit approval).
