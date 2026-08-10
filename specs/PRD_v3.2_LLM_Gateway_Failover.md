# PRD v3.2 — AI Fashion Designer (LLM Gateway + Provider Failover)

> **Status:** Implemented & verified (2026-07-13). Retro-spec — written after the work to match the repo's spec-first convention. Full design: `docs/superpowers/specs/2026-07-13-multi-provider-failover-design.md`. Decisions: DEC-024, DEC-025.

## 1. Context & Goals

Text LLM calls were scattered across `query_enrichment.py`, `stylist_agent.py`, and `agent/graph.py`, each building its own provider client with duplicated retry logic and no provider backup — a Vertex/Gemini outage broke every LLM feature.

Two goals, delivered together:
1. **Centralize** all LLM connectivity behind one gateway so the provider/model is swappable without touching business logic (LiteLLM integration).
2. **Resilience** — automatic failover to OpenAI when Vertex fails, the enterprise-grade way (reuse LiteLLM's native routing, no hand-rolled retry).

## 2. Scope

**In:** single gateway facade; LiteLLM `Router` for text with Vertex→OpenAI failover + cooldown; LangChain fallback chain for the tool-calling agent; cost tracking + LangSmith wiring; a single HIGH model for all tasks now.

**Out (deferred):** per-task capability tiers (config kept dormant for later); LiteLLM Proxy server; response caching; image-generation path (unchanged — it's a Gemini native-image model, not text).

## 3. Architecture

Public gateway API is unchanged — callers import `generate_text`, `get_chat_model`, `LLMGatewayError` from `src/llm_gateway/` and are not modified. Two engines live inside:

| Path | Engine | Failover behavior |
|---|---|---|
| **Text** (`generate_text`) — enrichment, stylist | LiteLLM `Router` | Vertex primary → OpenAI fallback, **per-request + cooldown** |
| **Agent** (`get_chat_model`) — LangGraph ReAct | LangChain `ChatGoogleGenerativeAI.with_fallbacks([ChatOpenAI])` | **per-request** (no cooldown), native tool-calling preserved |

Rationale for two engines: the Router returns completions (fine for text), but the agent needs a LangChain chat model with tool-calling that the Router can't hand back — so it uses LangChain's native `with_fallbacks`. Both are native mechanisms (no shims, DEC-023). `providers.py` exposes two builder functions (`build_text_router`, `build_chat_model`) rather than classes.

## 4. Configuration

| Setting | Default | Purpose |
|---|---|---|
| `llm_primary_model` | `gemini-2.5-pro` | Single Vertex HIGH model for all tasks |
| `llm_fallback_model` | *(set in `.env`)* | Single OpenAI failover model — **`gpt-5.6-terra`** (must support tool-calling) |
| `llm_fallback_enabled` | `true` | Master kill switch → `false` = Vertex-only |
| `llm_cooldown_seconds` / `llm_allowed_fails` | `60` / `3` | Router cooldown tuning |

Reuses existing `openai_api_key`. Per-task model settings remain in `config.py` but **dormant** (reserved for future tiers).

## 5. Key Decisions & Gotchas

- **DEC-024** — centralize behind `src/llm_gateway/` (LiteLLM integration).
- **DEC-025** — Vertex→OpenAI failover; single HIGH model; two engines.
- `reasoning_effort="none"` on the OpenAI branches: `gpt-5.6-terra` is a reasoning model and rejects function tools on `/v1/chat/completions` otherwise.
- `openai>=2.45.0` pinned (langchain-openai floor); litellm's `openai==2.30.0` pin is conservative, verified working at runtime.
- Cost tracking + LangSmith callbacks register once at gateway init; both fail-safe (a missing key or logging error never breaks a request).

## 6. Verification (manual, per project convention)

Verified with live Vertex + OpenAI calls: ① happy-path Vertex · ② text failover → OpenAI · ③ agent tool-calling failover → OpenAI · ④ both-fail → `LLMGatewayError` (graceful caller degradation) · ⑤ kill switch → Vertex-only. All pass.
