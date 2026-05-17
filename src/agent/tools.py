from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Annotated, Any, Iterator

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool, InjectedToolCallId  # InjectedToolCallId lives in langchain_core.tools (not langgraph)
from langgraph.prebuilt import InjectedState              # InjectedState lives in langgraph.prebuilt
from langgraph.types import Command

from src.agent.schemas import EnrichedQuery, Product, SearchFilters, SlotCheckResult, ToolTraceEntry
from src.agent.prompt_loader import get_tool_prompt
from src.config import Settings
from src.schemas import SearchFilters as LegacySearchFilters, SearchRequest
import src.query_enrichment as _qe_module
import src.search as _legacy_search

log = logging.getLogger(__name__)
settings = Settings()


@contextmanager
def _trace(tool_name: str) -> Iterator[dict[str, Any]]:
    """Capture latency and error for a single tool call.

    Caller wraps the resulting dict in a ToolTraceEntry and appends it to
    state['tool_trace'] via Command(update=...).  The operator.add reducer on
    that field ensures concurrent appends concatenate rather than overwrite.
    """
    start = time.perf_counter()
    entry: dict[str, Any] = {"tool_name": tool_name, "error": None}
    try:
        yield entry
    except Exception as exc:
        entry["error"] = repr(exc)
        log.exception("tool %s failed", tool_name)
        raise
    finally:
        entry["latency_ms"] = int((time.perf_counter() - start) * 1000)


@tool
def check_required_fields(
    state: Annotated[dict, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Check whether all required search fields are present in gathered_slots.

    Returns a SlotCheckResult with all_filled, missing_fields, and gathered_slots.
    Pure Python — no LLM call, cannot fail.
    """
    with _trace("check_required_fields") as entry:
        gathered: dict[str, str] = dict(state.get("gathered_slots") or {})
        required: list[str] = list(settings.agent_required_search_fields)
        missing: list[str] = [f for f in required if not gathered.get(f)]
        result = SlotCheckResult(
            all_filled=not missing,
            missing_fields=missing,
            gathered_slots=gathered,
        )

    return Command(
        update={
            "messages": [
                ToolMessage(
                    content=result.model_dump_json(),
                    tool_call_id=tool_call_id,
                )
            ],
            "tool_trace": [ToolTraceEntry(**entry)],
        }
    )


@tool
def ask_user(question: str) -> str:
    """Ask the user a single consolidated clarifying question that covers ALL missing required slots. The agent must NOT split missing slots across multiple ask_user calls — one question covers them all."""
    raise RuntimeError(
        "ask_user body must never execute — HumanInTheLoopMiddleware should have intercepted this call"
    )


@tool
def enrich_query(
    raw_query: str,
    gender: str,
    occasion: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Expand the user's raw query into a semantic search query, plus inferred color and garment-type filters. Pass the user's gender and occasion so the enrichment reflects the slot context."""
    with _trace("enrich_query") as entry:
        try:
            enriched_text: str = _qe_module.enrich_query(
                api_key=settings.gemini_api_key,
                model_name=settings.search_enrichment_model_name,
                query=raw_query,
                system_prompt=get_tool_prompt("query_enrichment_prompt"),
            )
            # The legacy function returns a plain enriched string — not structured.
            # We treat the whole string as semantic_query; color/category inference
            # requires a structured LLM call which is out of scope for this wrapper.
            # We return empty lists for inferred_colors and inferred_category so the
            # schema is satisfied; the semantic_query itself carries the expanded terms.
            enriched = EnrichedQuery(
                semantic_query=enriched_text,
                inferred_colors=[],
                inferred_category=[],
                reasoning="Query enriched via legacy enrich_query function.",
            )
        except Exception as exc:
            entry["error"] = repr(exc)
            log.warning("enrich_query failed, returning fallback: %s", exc)
            enriched = EnrichedQuery(
                semantic_query=raw_query,
                inferred_colors=[],
                inferred_category=[],
                reasoning="enrichment failed; using raw query",
            )

    filters = SearchFilters(
        colors=enriched.inferred_colors or None,
        occasion=occasion,
        category=enriched.inferred_category or None,
        gender=gender,
    )

    return Command(
        update={
            "messages": [
                ToolMessage(
                    content=enriched.model_dump_json(),
                    tool_call_id=tool_call_id,
                )
            ],
            "gathered_slots": {"gender": gender, "occasion": occasion},
            "current_filters": filters,
            "last_semantic_query": enriched.semantic_query,
            "tool_trace": [ToolTraceEntry(**entry)],
        }
    )


@tool
def search_products(
    semantic_query: str,
    filters: SearchFilters,
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Search the product catalog for items matching the semantic query and filters. Returns at most 5 products. The LLM cannot override the result-count cap. Set filters to constrain by colors, occasion, category, or gender; leave fields None to relax the constraint. strict_mode auto-activates when any filter field is non-None."""
    with _trace("search_products") as entry:
        strict = any(
            getattr(filters, f) for f in ("colors", "occasion", "category", "gender")
        )
        products: list[Product] = []
        try:
            # Build legacy SearchRequest — gender is agent-side only; legacy filters
            # support colors/occasion/category. strict_mode passed via request flag.
            legacy_filters = LegacySearchFilters(
                colors=filters.colors,
                occasion=filters.occasion,
                category=filters.category,
                # gender not in legacy SearchFilters — omitted intentionally
            )
            request = SearchRequest(
                query=semantic_query,
                top_k=settings.agent_max_results,
                strict_mode=strict,
                filters=legacy_filters if strict else None,
            )
            response = _legacy_search.run_search(
                openai_api_key=settings.openai_api_key,
                pinecone_api_key=settings.pinecone_api_key,
                pinecone_index_name=settings.pinecone_index_name,
                best_match_score_threshold=settings.best_match_score_threshold,
                request=request,
            )
            for r in response.results[: settings.agent_max_results]:
                products.append(_to_product(r, gender=filters.gender))
        except Exception as exc:
            entry["error"] = repr(exc)
            log.warning("search_products failed: %s", exc)
            products = []

    return Command(
        update={
            "messages": [
                ToolMessage(
                    content=f"{len(products)} products",
                    tool_call_id=tool_call_id,
                )
            ],
            "last_products": products,
            "current_filters": filters,
            "tool_trace": [ToolTraceEntry(**entry)],
        }
    )


def _to_product(raw: Any, gender: str | None = None) -> Product:
    """Map a legacy SearchResultItem to an agent Product."""
    if hasattr(raw, "model_dump"):
        raw = raw.model_dump()
    matched = raw.get("matched_attributes") or {}
    if hasattr(matched, "model_dump"):
        matched = matched.model_dump()
    return Product(
        product_id=str(raw.get("product_id") or ""),
        image_path=raw.get("image_path") or "",
        score=float(raw.get("score") or 0.0),
        category=matched.get("category") or raw.get("category") or "",
        colors=list(matched.get("colors") or raw.get("colors") or []),
        occasion=matched.get("occasion") or raw.get("occasion") or "",
        style_tags=list(raw.get("style_tags") or []),
        caption=raw.get("caption") or "",
        gender=gender,
    )
