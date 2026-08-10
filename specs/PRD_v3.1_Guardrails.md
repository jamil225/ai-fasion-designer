# PRD v3.1 — AI Fashion Designer (Guardrails)

## 1. Context and Goals
Phase 3.1 focuses on bringing production-grade guardrails to the AI Fashion Designer ReAct agent. The goal is to ensure safety, relevance, and robustness against malicious or out-of-scope inputs, as well as prevent hallucinations and data leakage in the output.

Following the principle of "crawl, walk, run", we will implement the guardrails in a phased manner. Phase 1 will lay the foundation, establish the design patterns, and implement a single guardrail. Future phases will build out the comprehensive defense-in-depth strategy.

## 2. Guardrail Strategy & Design
We follow a defense-in-depth, layered strategy:
1. **Input Guardrails**: Executed via FastAPI Middleware (Fast reject before hitting the LLM).
2. **Output Guardrails**: Executed via LangGraph Post-Nodes (Validate LLM outputs before returning to the user).
3. **Architectural Guardrails**: Executed via LangGraph Pre-Nodes and strict Pydantic tool schemas.

### 2.1. Tooling Selection
Based on a comprehensive research spike of industry standards:
- **OpenAI Moderation API**: Selected for fast, baseline toxicity and safety checks. It is free, has low latency (~100ms), and the SDK is already in our stack.
- **Guardrails AI**: Selected for domain-specific, programmatic validation (Topic containment, PII scanning, schema validation, hallucination checking). Integrates seamlessly with LangChain.

*Note: NeMo Guardrails was evaluated but rejected due to the complexity overhead of learning its Colang DSL for a project of this scope.*

### 2.2. Architectural Patterns (Extensibility)
To ensure we can plug in any other model or library later (e.g., switching to LLM Guard or a custom Gemini Flash classifier) without rewriting the core application, the implementation will use the **Strategy Pattern**:
- A base abstract interface (e.g., `BaseGuardrail`).
- Specific implementations (e.g., `OpenAIModerationGuardrail`).
- A central `GuardrailRegistry` or manager that reads the configuration and executes the active guards.

## 3. Configuration Management
All guardrails will be driven by a YAML configuration file. This allows for a global kill-switch (to bypass all checks during debugging for zero-latency) and per-guard toggling to easily tune false positives in production.

**Draft `config/guardrails.yaml`**:
```yaml
guardrails:
  enabled: true          # Master kill-switch. If false, ALL guardrails are bypassed.
  
  input:
    enabled: true
    openai_moderation: true
    # Future Phase items:
    # prompt_injection: true
    # topic_containment: true
    # max_message_length: 500
    
  output:
    enabled: true
    # Future Phase items:
    # hallucination_check: true
    # fashion_relevance: true
    # toxicity_check: true
    # pii_leakage_scan: true
```

## 4. Implementation Phasing

### 4.1. Phase 1 Scope (Current)
Build the foundational scaffolding and prove the pattern with a single guardrail.
- **Tasks**:
  1. Create the `config/guardrails.yaml` structure and parsing logic.
  2. Implement the modular `BaseGuardrail` strategy pattern.
  3. Implement **OpenAI Moderation API** as the single Phase 1 input guardrail (FastAPI Middleware).
  4. Ensure that toggling `enabled: false` in the YAML completely bypasses the middleware.

### 4.2. Future Scope (Phase 2 & Beyond)
Once Phase 1 is proven, we will implement the full defense-in-depth suite.
- **Input Guardrails**:
  - *Prompt Injection*: Layered approach (Regex fast-reject → ML classifier fallback).
  - *Topic Containment*: LLM classifier (using Gemini Flash) per request to reject non-fashion queries gracefully.
- **Output Guardrails**:
  - *Hallucination Prevention*: Verify all mentioned products actually exist in Pinecone results.
  - *Fashion Relevance*: Verify the final response stays on-topic.
  - *PII Leakage Scan*: Ensure no sensitive data (like API keys or system prompts) leaks out.
- **Security Vulnerability Patching**:
  - Fix the path traversal vulnerability in `GET /v1/images/{filename}` (where `..` could allow reading arbitrary server files).
- **Rate Limiting**:
  - Implement token bucket or similar API rate limiting to prevent abuse.
