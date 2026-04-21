# CLAUDE.md — AI Fashion Designer RAG Application

## Project Overview

**PRD**: `PRD_v2_Phase1_Vision_First_RAG.md` — single source of truth for all requirements, API contracts, architecture, and decision rationale. Read it fully before writing any code.

## Who I Am

Senior software engineer (Java/Spring Boot enterprise background). Building this Python prototype to learn and ship quickly. I must be able to explain every architectural and code decision — no black-box magic. If a pattern is used, I should understand why it was chosen.

## How To Work (Mandatory Process)

Follow this exact workflow for implementation:

1. **Read the PRD fully** before starting any work.
2. **Create a task list** — break the milestones below into concrete, actionable tasks using `TaskCreate`.
3. **Work task by task** — pick one task, mark it `in_progress`, complete it, mark it `completed`, then move to the next. Never work on multiple tasks simultaneously.
4. **Each completed task must produce working code** — testable via Swagger UI before moving on.
5. **Ask me if uncertain** — never assume requirements not in the PRD.

### Milestone Order (Break These Into Tasks)

1. Config + health endpoint + auth middleware
2. Ingestion API + folder scanner + dedup
3. Vision pipeline + taxonomy normalization
4. Embedding + Pinecone upsert
5. Search API with soft/strict modes
6. End-to-end manual validation via Swagger

## Skills (Use When Appropriate)

Use these skills strictly when their domain applies. Do not skip them for relevant work:

```
~/.claude/skills/
├── ai-engineer/SKILL.md              # LLM app patterns, agent architecture
├── rag-engineer/SKILL.md             # RAG system design, retrieval optimization
├── rag-implementation/SKILL.md       # RAG pipeline implementation
├── embedding-strategies/SKILL.md     # Embedding model selection, chunking
├── hybrid-search-implementation/SKILL.md  # Combined vector + keyword search
├── vector-database-engineer/SKILL.md # Pinecone setup, indexing, queries
├── similarity-search-patterns/SKILL.md   # Nearest neighbor, search optimization
├── context-manager/SKILL.md          # Context engineering, memory systems
├── langchain-architecture/SKILL.md   # LLM framework patterns
├── llm-evaluation/SKILL.md           # Quality metrics, benchmarking
├── prompt-engineering-patterns/SKILL.md  # Prompt design (Gemini Vision prompt)
├── brainstorming/SKILL.md            # Design validation, architecture review
├── workflow-automation/SKILL.md      # Pipeline orchestration patterns
```

## Development Standards

### Python Style
- Python 3.11+. Type hints on all function signatures.
- Pydantic models for all request/response schemas.
- `async def` for FastAPI route handlers; ingestion is synchronous sequential.
- Prefer functions and modules over classes. No abstract base classes or factory patterns.

### Error Handling
- Catch specific exceptions, never bare `except`.
- 3 retries with exponential backoff (1s, 2s, 4s) for Gemini/Pinecone transient failures.
- Failed images logged and skipped — never crash the service.

### Configuration
- All secrets via `.env` + `pydantic-settings`. No hardcoded keys/URLs.
- Image folder path from config only — NEVER from API requests.

### Security
- API key auth (`X-API-Key` header) on all endpoints except `/v1/health`.
- Never expose full file paths in responses — filename only in errors.
- `.env` in `.gitignore`. No PII.

### Naming
- Files/functions: `snake_case` | Models: `PascalCase` | Constants: `UPPER_SNAKE_CASE`
- API routes: `/v1/` prefix

## What NOT To Do

- Do NOT write unit/integration tests — manual Swagger UI testing only.
- Do NOT implement async/concurrent ingestion — synchronous sequential only.
- Do NOT add any database (SQLite, PostgreSQL) — Pinecone only.
- Do NOT build a frontend — Swagger `/docs` is the interface.
- Do NOT create dead-letter queues, background workers, or retry persistence.
- Do NOT add CORS, rate limiting, or advanced middleware unless asked.
- Do NOT add logging frameworks — use Python built-in `logging`.
- Do NOT create Docker, CI/CD, pre-commit hooks, or linter config unless asked.
- Do NOT add docstrings everywhere — only where logic isn't self-evident.
- Do NOT generate README.md unless asked.
- Do NOT introduce additional frameworks, ORMs, task queues, or libraries not in the PRD tech stack.
- Do NOT create `utils/`, `helpers/`, `common/` directories. Keep flat in `src/`.
- Do NOT build anything marked "Phase II" in the PRD.

## When In Doubt

- Read the PRD.
- If not in the PRD, ask me.
- Prefer simple over clever.
- If about to add something not explicitly required, stop and ask.
