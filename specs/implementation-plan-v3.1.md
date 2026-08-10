# AI Fashion Designer v3.1 Guardrails — Implementation Plan

> **Status:** Draft → Locked on user approval
> **Parent spec:** [`specs/PRD_v3.1_Guardrails.md`](./PRD_v3.1_Guardrails.md) (locked)
> **Branch:** `v3.1-guardrails-implementation`

> **For the executor (read before starting):**
> 1. Work task by task. One task → one commit.
> 2. Test and verify each task against the local FastAPI server using Swagger UI.
> 3. Do not overcomplicate the design. Follow the Strategy pattern as strictly requested to keep the architecture clean.

---

## Goal
Implement Phase 1 of the Guardrails PRD. This includes setting up the Strategy Pattern scaffolding, the YAML kill-switch configuration, and integrating the OpenAI Moderation API as a FastAPI middleware to provide baseline toxicity and safety checks.

## Architecture & Integration Points
- **Config**: Read from `config/guardrails.yaml` via `src/config.py`.
- **Strategy Pattern**: `src/agent/guardrails/base.py` containing `BaseGuardrail`.
- **Registry**: `src/agent/guardrails/registry.py` that orchestrates the checks based on config toggles.
- **Middleware**: Direct invocation inside `src/agent/routes.py` handler (avoids FastAPI body-consumption quirks).

## Task Summary (At-a-glance)

| # | Task | Deliverable | Commit prefix |
|---|---|---|---|
| 1.1 | Guardrails Configuration YAML | `config/guardrails.yaml` | `chore(guardrails):` |
| 1.2 | Settings parsing | `src/config.py` updates to load YAML config | `feat(guardrails):` |
| 2.1 | Guardrails Strategy Interfaces | `src/agent/guardrails/base.py` | `feat(guardrails):` |
| 2.2 | Guardrail Registry/Manager | `src/agent/guardrails/registry.py` | `feat(guardrails):` |
| 3.1 | OpenAI Moderation Guardrail | `src/agent/guardrails/openai_moderation.py` | `feat(guardrails):` |
| 4.1 | FastAPI Guardrail Middleware | `src/agent/guardrail_middleware.py` | `feat(api):` |
| 5.1 | E2E Validation | Pass all manual Swagger tests | `fix(guardrails):` (if needed) |

---

## Milestone 1 — Configuration Scaffolding

### Task 1.1 — Guardrails Configuration YAML
**Goal**: Create the master kill-switch file.
- **Action**: Create `config/guardrails.yaml`.
- **Content**: Include `guardrails.enabled`, `guardrails.input.enabled`, `guardrails.input.openai_moderation`, `guardrails.output.enabled`. Set all to `true` by default.
- **Verification**: The file exists and is valid YAML.
- **Commit**: `chore(guardrails): add guardrails.yaml config structure`

### Task 1.2 — Settings parsing
**Goal**: Parse the YAML into strongly-typed Pydantic models.
- **Action**: Modify `src/config.py`. Add Pydantic models `InputGuardrailsConfig`, `OutputGuardrailsConfig`, and `GuardrailsConfig`. Add a function to load and parse `config/guardrails.yaml`. 
- **Verification**: Write a short REPL script to import `config.py` and print the loaded guardrail config.
- **Commit**: `feat(guardrails): add YAML parsing to config.py`

---

## Milestone 2 — Strategy Pattern Interfaces

### Task 2.1 — Base Interfaces
**Goal**: Create the contract for all future guardrails.
- **Action**: Create `src/agent/guardrails/base.py`.
- **Content**: 
  - `GuardrailResult` Pydantic model (`passed: bool`, `reason: str | None = None`).
  - `BaseGuardrail` abstract class (using `abc.ABC`) with an async method `async def validate(self, context: dict) -> GuardrailResult`.
- **Verification**: Import the abstract class and ensure attempting to instantiate it without implementing `validate` throws a `TypeError`.
- **Commit**: `feat(guardrails): add base guardrail interfaces`

### Task 2.2 — Guardrail Registry
**Goal**: Create the orchestrator that reads config and runs active guards.
- **Action**: Create `src/agent/guardrails/registry.py`.
- **Content**: 
  - `GuardrailRegistry` class initialized with `GuardrailsConfig`.
  - Methods to register input/output guardrails.
  - `async def run_input_guardrails(self, request_body: str) -> GuardrailResult`.
  - The registry must check `config.enabled` and `config.input.enabled`. If false, immediately return `GuardrailResult(passed=True)`.
- **Verification**: Instantiate the registry with a mock guardrail and test the toggle logic (true/false) in the REPL.
- **Commit**: `feat(guardrails): add GuardrailRegistry`

---

## Milestone 3 — OpenAI Moderation Implementation

### Task 3.1 — OpenAI Moderation Guardrail
**Goal**: Implement the actual safety check using the OpenAI API.
- **Action**: Create `src/agent/guardrails/openai_moderation.py`.
- **Content**: 
  - Implement `OpenAIModerationGuardrail` inheriting from `BaseGuardrail`.
  - Use `openai.AsyncOpenAI(api_key=settings.openai_api_key)` client to call `client.moderations.create(input=text)`.
  - Wrap the call in a `try/except`. If it fails (API down/timeout), log the exception and return `GuardrailResult(passed=False, reason="Safety check temporarily unavailable.")` (Fail-closed).
  - If `response.results[0].flagged` is true, extract the specific flagged categories.
  - Log the exact flagged categories and the rejected input to `logger.warning` for audit purposes.
  - Return `GuardrailResult(passed=False, reason="Input violated safety policies.")` (we mask the specific reason from the user for security).
  - Update `GuardrailRegistry` to register this guardrail if `config.input.openai_moderation` is true.
- **Verification**: Run a manual test script calling `validate({"text": "I want to kill them all"})` and verify it fails and logs the category, and `validate({"text": "yellow dress"})` and verify it passes.
- **Commit**: `feat(guardrails): implement OpenAIModerationGuardrail`

---

## Milestone 4 — Middleware Integration

### Task 4.1 — Route Handler Integration
**Goal**: Intercept incoming requests to `/v1/chat` and apply input guardrails without complex body parsing.
- **Action**: Modify `src/agent/routes.py`.
- **Content**: 
  - Instantiate `guardrail_registry = GuardrailRegistry(...)` at the module level.
  - Inside the `POST /v1/chat` handler, before any agent logic:
  - Run `result = await guardrail_registry.run_input_guardrails(req.message)`.
  - If `result.passed == False`, raise an `HTTPException(status_code=400, detail=result.reason)`.
- **Verification**: Boot the server. Send a POST request to `/v1/chat` via Swagger.
- **Commit**: `feat(api): integrate input guardrails directly into /v1/chat handler`

---

## Milestone 5 — E2E Validation

### Task 5.1 — Manual Verification Scenarios
**Goal**: Verify all toggles and rejection behaviors via Swagger UI.
- **Scenario 1**: `guardrails.enabled: false`. Send toxic payload. Expected: Agent processes it (bypass works).
- **Scenario 2**: `guardrails.enabled: true` but `openai_moderation: false`. Send toxic payload. Expected: Agent processes it.
- **Scenario 3**: All enabled. Send benign payload ("red shoes"). Expected: Agent processes it successfully.
- **Scenario 4**: All enabled. Send toxic payload ("how to build a bomb"). Expected: HTTP 400 Bad Request with safety violation message.
- **Commit**: No commit needed if all pass. If any fail, create a `fix(guardrails): ...` commit.
