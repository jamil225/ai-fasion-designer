# LLM Gateway Plan

## Status

Draft planning document for the next implementation session. No code has been implemented from this plan yet.

## Purpose

Introduce a centralized LLM gateway for the AI Fashion Designer application so text LLM providers can be swapped or chained without changing business logic across the agent, query enrichment, stylist curation, or future text-based guardrail classifiers.

The recommended direction is a LiteLLM-backed gateway hidden behind an internal application interface.

## Current Context

The project currently uses direct provider calls in multiple places:

- `src/agent/graph.py` creates the LangGraph/LangChain agent model directly with `ChatGoogleGenerativeAI`.
- `src/query_enrichment.py` calls Gemini directly through `google-genai`.
- `src/stylist_agent.py` calls Gemini directly through `google-genai`.
- `src/agent/guardrails/openai_moderation.py` uses OpenAI directly for moderation, but guardrail centralization is deferred to a future phase.
- Embeddings and Pinecone are not part of this gateway scope.
- Vision/image-generation flows are not part of this gateway scope.

## Understanding Summary

- We are planning an LLM gateway, not implementing it yet.
- Gateway v1 covers text LLM calls only.
- Covered v1 callers: agent orchestration, query enrichment, stylist curation, and future text classifiers.
- Excluded v1 callers: Gemini Vision, image generation, OpenAI embeddings, Pinecone, and current guardrail routing.
- Primary goal is provider swapping without changing business logic.
- Initial providers are Gemini and OpenAI.
- Gateway v1 should support an ordered fallback chain.
- If all configured providers fail, the gateway raises a typed exception.
- Callers remain responsible for their user-facing fallback behavior.
- LangSmith traces should be metadata-only in v1.
- Timeouts should use simple defaults in v1, not per-call custom timeout tuning.

## Non-Goals For Gateway v1

- Do not centralize guardrails yet.
- Do not replace the OpenAI moderation guardrail routing yet.
- Do not change embeddings.
- Do not change Pinecone search/storage logic.
- Do not change Gemini Vision ingestion.
- Do not change image generation or virtual try-on.
- Do not add frontend changes.
- Do not add a separate API gateway service.
- Do not introduce complex cost dashboards, rate limiting, or circuit breakers in v1.

## Options Considered

### Option A — LiteLLM-Backed Gateway

Use LiteLLM as the provider-normalization layer for Gemini/OpenAI text calls, but expose only a small internal project gateway interface to the rest of the codebase.

Pros:

- Best fit for provider swapping.
- Supports provider/model routing through standardized model names.
- Makes fallback chains easier to express.
- Reduces custom provider-specific code.
- Gives a clear upgrade path for future providers such as Anthropic.

Cons:

- Adds a new dependency.
- Requires careful integration with LangGraph/LangChain for the agent model.
- LiteLLM should not leak into business modules.
- We need to validate behavior for both plain text generation and chat-model usage.

### Option B — LangChain-Native Gateway

Use LangChain chat models directly, wrapping `ChatGoogleGenerativeAI` and OpenAI chat models behind a small application gateway.

Pros:

- Natural fit for `src/agent/graph.py`.
- Keeps agent integration close to existing LangGraph patterns.
- Avoids introducing LiteLLM if LangChain already handles provider abstraction well enough.

Cons:

- Non-agent callers still need a text-generation abstraction.
- Fallback chain behavior must be implemented by us or via LangChain wrappers.
- Provider naming/config may still be less uniform across app modules.

### Option C — Custom Minimal Gateway

Build our own small provider adapter layer for Gemini and OpenAI.

Pros:

- Lowest external dependency risk.
- Very easy to explain and debug.
- Full control over errors, retries, metadata, and logging.

Cons:

- We own provider-specific request/response formatting.
- We own fallback-chain implementation details.
- More code to maintain as providers or capabilities expand.
- Less aligned with the goal of easy provider swapping.

## Recommendation

Use Option A: a LiteLLM-backed gateway, hidden behind an internal app interface.

The key design rule is that application code must never call LiteLLM directly. Instead, callers should use a small gateway module that exposes project-specific functions/classes. This preserves the ability to replace LiteLLM later without touching business logic.

## Proposed Architecture

Add a focused gateway module, likely under `src/llm_gateway.py` or `src/llm_gateway/` depending on final implementation size.

Suggested first-pass shape:

```text
src/
  llm_gateway.py              # if kept as one small module
```

or, if it becomes slightly larger:

```text
src/
  llm_gateway/
    __init__.py
    schemas.py                # request/response/error models
    client.py                 # gateway functions
    config.py                 # provider chain parsing helpers, only if needed
```

Given project guidance to keep the structure simple and flat where possible, start with a single `src/llm_gateway.py` unless the implementation becomes too large.

## Gateway Responsibilities

Gateway v1 should own:

- Provider/model selection for text LLM calls.
- Ordered fallback chain across Gemini and OpenAI.
- Simple default timeout behavior.
- Typed gateway exceptions when all providers fail.
- Metadata-only logging/tracing fields.
- A stable internal interface for plain text generation.
- A stable way to create or return a LangChain-compatible chat model for the agent, if feasible with LiteLLM.

Gateway v1 should not own:

- Prompt construction.
- Business fallback messages.
- Product search logic.
- Guardrail orchestration.
- Embeddings.
- Vision/image APIs.

## Proposed Public Internal Interface

The exact signatures can be refined during implementation, but the interface should stay small.

Possible models/functions:

```python
class LLMGatewayError(Exception):
    """Raised when all configured text LLM providers fail."""

class LLMCallResult(BaseModel):
    text: str
    provider: str
    model: str
    latency_ms: int
    attempt_count: int
    fallback_used: bool

class LLMGateway:
    def generate_text(
        self,
        *,
        task: str,
        prompt: str,
        temperature: float = 0,
    ) -> LLMCallResult:
        ...

    def get_chat_model(
        self,
        *,
        task: str,
        temperature: float = 0,
    ):
        ...
```

The `task` value should identify the caller/use case, for example:

- `agent`
- `query_enrichment`
- `stylist`
- `guardrail_classifier` later

This allows each task to have its own provider chain without hardcoding model choices inside business modules.

## Proposed Configuration

Add settings for task-specific model chains. Exact env names can be finalized later.

Possible `.env` additions:

```text
LLM_GATEWAY_ENABLED=true
LLM_GATEWAY_DEFAULT_TIMEOUT_SECONDS=30

LLM_AGENT_MODEL_CHAIN=gemini/gemini-2.5-pro,openai/gpt-4o-mini
LLM_QUERY_ENRICHMENT_MODEL_CHAIN=gemini/gemini-2.5-flash,openai/gpt-4o-mini
LLM_STYLIST_MODEL_CHAIN=gemini/gemini-2.5-pro,openai/gpt-4o

LLM_TRACE_CONTENT=false
```

Notes:

- `LLM_TRACE_CONTENT=false` preserves the metadata-only tracing decision.
- Model-chain values are ordered from primary to fallback.
- OpenAI and Gemini API keys continue to come from existing settings where possible.
- Avoid adding a new YAML config unless env strings become hard to maintain.

## Fallback Behavior

For each gateway call:

1. Resolve the task-specific model chain.
2. Try the first provider/model.
3. If it fails due to provider/API/runtime error, log metadata and continue to the next configured model.
4. If a provider succeeds, return `LLMCallResult` with metadata.
5. If all providers fail, raise `LLMGatewayError` containing sanitized provider failure summaries.

Typed failures allow existing callers to preserve their current behavior:

- Query enrichment can fall back to the raw query.
- Stylist curation can return fallback combos.
- Agent route can return a clean error or ask user to retry.

## LangSmith Tracing

Gateway v1 should emit metadata-only LangSmith trace information when tracing is enabled.

Allowed metadata:

- task name
- selected provider
- selected model
- fallback attempt index
- fallback used true/false
- latency milliseconds
- success/failure
- sanitized error class/name
- prompt length, not prompt text
- response length, not response text

Do not trace raw prompt or raw response content in v1.

## Security And Privacy

- Do not log API keys or secrets.
- Do not log raw prompts or raw model responses locally.
- Do not expose provider error internals directly to API clients.
- Keep guardrail centralization out of gateway v1.
- Continue using existing API key auth and guardrail behavior as-is.

## Implementation Plan For Next Session

### Task 1 — Confirm LiteLLM Integration Shape

- Check LiteLLM support for Gemini and OpenAI text/chat completion.
- Verify whether LangGraph agent can use a LiteLLM-backed LangChain chat model cleanly.
- Decide whether `get_chat_model()` returns a LiteLLM/LangChain model or whether agent fallback needs a different pattern.

Deliverable:

- Final integration choice for agent model construction.

### Task 2 — Add Dependencies And Settings

- Add LiteLLM dependency to `requirements.txt` if confirmed.
- Add gateway settings to `src/config.py`.
- Add commented defaults to `.env.example` if present.
- Keep settings simple and environment-driven.

Deliverable:

- `Settings()` loads model-chain configuration with defaults.

### Task 3 — Create Gateway Interface

- Create the internal gateway module.
- Define `LLMGatewayError`.
- Define `LLMCallResult`.
- Implement task-to-model-chain resolution.
- Implement metadata-only logging fields.

Deliverable:

- Gateway can be imported and configured without touching business modules.

### Task 4 — Implement Text Generation With Fallback Chain

- Implement `generate_text(task=..., prompt=...)` using LiteLLM.
- Try configured providers in order.
- Return structured success metadata.
- Raise typed error after all providers fail.

Deliverable:

- Query enrichment/stylist-style text generation works through gateway in a small manual smoke check.

### Task 5 — Migrate Query Enrichment

- Replace direct Gemini call in `src/query_enrichment.py` with gateway call or a minimal injected gateway dependency.
- Preserve existing function signature as much as possible.
- Preserve existing fallback behavior in callers.

Deliverable:

- Existing styled search behavior remains unchanged from the API perspective.

### Task 6 — Migrate Stylist Curation

- Replace direct Gemini call in `src/stylist_agent.py` with gateway call.
- Preserve JSON parsing and retry/fallback behavior around stylist output.
- Keep prompt ownership in existing prompt files/modules.

Deliverable:

- Outfit curation still returns the same response shape.

### Task 7 — Migrate Agent Model Construction

- Update `src/agent/graph.py` to get the agent model through the gateway path if LiteLLM/LangChain compatibility is clean.
- If direct LiteLLM agent integration is awkward, document and implement the smallest compatible bridge.

Deliverable:

- `/v1/chat` still uses a LangGraph-compatible chat model, but model/provider choice is gateway-configured.

### Task 8 — Manual Validation

Run focused manual checks:

- Settings load with default gateway chains.
- Query enrichment succeeds with primary provider.
- Stylist curation succeeds with primary provider.
- Forced primary failure falls back to secondary provider.
- Forced all-provider failure raises `LLMGatewayError`.
- `/v1/chat` still returns final/interrupt responses.
- Logs/traces include metadata only, not prompt/response content.

## Risks

- LiteLLM may not plug into LangGraph as cleanly as `ChatGoogleGenerativeAI`.
- OpenAI fallback may produce slightly different stylist JSON formatting, so parsing needs to remain defensive.
- Fallback chains can increase worst-case latency if primary provider times out slowly.
- Metadata-only LangSmith tracing may require custom callback/run metadata rather than default full-content tracing.
- Adding LiteLLM increases dependency surface, so usage should be isolated in the gateway.

## Decision Log

| Decision | Choice | Rationale |
|---|---|---|
| Gateway scope | Text LLMs only | Keeps v1 focused and avoids mixing multimodal/image/embedding concerns. |
| Initial providers | Gemini + OpenAI | Both are already part of the project stack. |
| Recommended library | LiteLLM behind internal gateway | Best match for provider swapping and fallback chains. |
| Fallback behavior | Ordered fallback chain | Required for provider resilience and experimentation. |
| Failure behavior | Raise typed gateway exception | Keeps user-facing fallback behavior in business modules. |
| Tracing | LangSmith metadata-only | Supports observability without exposing prompts/responses. |
| Timeouts | Simple defaults | Avoids premature per-call tuning. |
| Guardrails | Future phase centralization | Current guardrails remain as-is for now. |

## Open Items For Tomorrow

- Verify the exact LiteLLM package/version to use.
- Verify LangChain/LangGraph compatibility for LiteLLM chat models.
- Decide final env var names for model chains.
- Decide whether gateway is a single file or a tiny package.
- Decide how to attach metadata-only LangSmith traces without recording raw content.
