from __future__ import annotations

import logging
import time
import uuid
from contextlib import contextmanager
from typing import Annotated, Any, Iterator

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool, InjectedToolCallId  # InjectedToolCallId lives in langchain_core.tools (not langgraph)
from langgraph.prebuilt import InjectedState              # InjectedState lives in langgraph.prebuilt
from langgraph.types import Command, interrupt

try:
    from langsmith import traceable as _traceable
except ImportError:
    # Graceful fallback if langsmith not installed
    def _traceable(**_kw):  # type: ignore[misc]
        def _wrap(fn):
            """
            Return the function unchanged.
            
            Returns:
                The original function.
            """
            return fn
        return _wrap

from src.agent.schemas import EnrichedQuery, OutfitCombo, Product, SearchFilters, SlotCheckResult, ToolTraceEntry
from src.agent.prompt_loader import get_tool_prompt
from src.config import Settings
from src.schemas import SearchFilters as LegacySearchFilters, SearchRequest
import src.query_enrichment as _qe_module
import src.search as _legacy_search
import src.stylist_agent as _legacy_stylist

log = logging.getLogger(__name__)
settings = Settings()


# ---------------------------------------------------------------------------
# LangSmith child spans — rich data visible in portal without leaking to LLM
# ---------------------------------------------------------------------------

@_traceable(name="pinecone_search_results", run_type="retriever")
def _span_search_results(
    query: str,
    filters: dict,
    products: list[dict],
) -> dict:
    """Child span: full Pinecone results visible in LangSmith, not in ToolMessage."""
    return {"query": query, "filters": filters, "result_count": len(products), "products": products}


@_traceable(name="outfit_combo_results", run_type="chain")
def _span_combo_results(combos: list[dict]) -> dict:
    """Child span: full curated combos visible in LangSmith, not in ToolMessage."""
    return {"combo_count": len(combos), "combos": combos}


@contextmanager
def _trace(tool_name: str) -> Iterator[dict[str, Any]]:
    """
    Capture timing and errors for a tool execution.
    
    Parameters:
        tool_name (str): Name of the tool being measured.
    
    Yields:
        dict[str, Any]: Trace entry containing the tool name, error status, and elapsed latency in milliseconds.
    
    Raises:
        Exception: Re-raises any exception raised during the tool execution after recording it.
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
    """
    Check whether all required search fields have been gathered.
    
    Returns:
        Command: A state update containing the serialized slot check result and tool trace.
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
        log.info("check_required_fields: all_filled=%s, missing=%s", result.all_filled, missing)

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
    """
    Pause the workflow to request the user's answer to a consolidated clarifying question.
    
    Parameters:
        question (str): The clarifying question covering the required information.
    
    Returns:
        str: The user's response.
    """
    # v0.3 HITL primitive: interrupt() pauses the graph, surfaces the payload
    # via __interrupt__ on the response, and the client resumes with
    # Command(resume=<reply>) — the resume value becomes this call's return.
    log.info("ask_user: question='%s'", question)
    reply = interrupt({"type": "ask_user", "question": question})
    log.info("ask_user: reply='%s'", reply)
    return reply if isinstance(reply, str) else str(reply)


@tool
def enrich_query(
    raw_query: str,
    gender: str,
    occasion: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """
    Expand a raw apparel query into a semantic search query and associated filters.
    
    Parameters:
    	raw_query (str): The user's original search query.
    	gender (str): The user's selected gender context.
    	occasion (str): The user's selected occasion.
    
    Returns:
    	Command: A graph state update containing the enriched query, search filters, gathered slots, and tool trace.
    """
    with _trace("enrich_query") as entry:
        try:
            enriched_text: str = _qe_module.enrich_query(
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
    """
    Search the product catalog using a semantic query and optional filters.
    
    Parameters:
        semantic_query (str): The query describing the desired products.
        filters (SearchFilters): Filters for narrowing results by color, occasion, category, or gender.
    
    Returns:
        Command: A graph state update containing the matching products, applied filters, result summary, and tool trace.
    """
    with _trace("search_products") as entry:
        log.info("search_products: query='%s', gender=%s, occasion=%s", semantic_query, filters.gender, filters.occasion)
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
            if strict and not response.results:
                log.info(
                    "strict agent search returned 0 products; retrying soft search"
                )
                entry["error"] = "strict_search_zero_results_soft_fallback"
                response = _legacy_search.run_search(
                    openai_api_key=settings.openai_api_key,
                    pinecone_api_key=settings.pinecone_api_key,
                    pinecone_index_name=settings.pinecone_index_name,
                    best_match_score_threshold=settings.best_match_score_threshold,
                    request=SearchRequest(
                        query=semantic_query,
                        top_k=settings.agent_max_results,
                        strict_mode=False,
                        filters=None,
                    ),
                )
            for r in response.results[: settings.agent_max_results]:
                products.append(_to_product(r, gender=filters.gender))
        except Exception as exc:
            entry["error"] = repr(exc)
            log.warning("search_products failed: %s", exc)
            products = []

    log.info("search_products: returned %d products", len(products))

    # Emit child span with full product data for LangSmith visibility.
    # ToolMessage stays minimal so the LLM cannot see or corrupt product fields.
    _span_search_results(
        query=semantic_query,
        filters=filters.model_dump(),
        products=[p.model_dump() for p in products],
    )

    return Command(
        update={
            "messages": [
                ToolMessage(
                    content=f"{len(products)} products found",
                    tool_call_id=tool_call_id,
                )
            ],
            "last_products": products,
            "current_filters": filters,
            "tool_trace": [ToolTraceEntry(**entry)],
        }
    )


def _to_product(raw: Any, gender: str | None = None) -> Product:
    """
    Convert a legacy search result into an agent product.
    
    Parameters:
    	raw (Any): Legacy search result data or a model that can be converted to a mapping.
    	gender (str | None): Gender associated with the product.
    
    Returns:
    	Product: Product populated from the search result data.
    """
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


@tool
def curate_outfits(
    state: Annotated[dict, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """
    Curate outfit combinations from the products stored in the current graph state.
    
    Parameters:
    	state (dict): Graph state containing the products from the latest search.
    	tool_call_id (str): Identifier for the tool call associated with the state update.
    
    Returns:
    	Command: State update containing the curated outfit combinations, a summary tool message, and trace information.
    """
    # Products come from state (single source of truth from Pinecone).
    # The LLM must NOT pass product data — it would hallucinate image_path and product_id.
    products: list[Product] = list(state.get("last_products") or [])
    with _trace("curate_outfits") as entry:
        combos: list[OutfitCombo] = []
        if not products:
            log.info("curate_outfits: 0 products in state, skipping")
            # Empty input -> empty output, no fallback combos
            pass
        else:
            try:
                # Build a product_id -> Product lookup for resolving legacy ID references
                product_map: dict[str, Product] = {p.product_id: p for p in products}
                # Legacy function expects list[dict] with all product fields
                products_as_dicts = [
                    {
                        "product_id": p.product_id,
                        "image_path": p.image_path,
                        "category": p.category,
                        "colors": p.colors,
                        "occasion": p.occasion,
                        "style_tags": p.style_tags,
                        "caption": p.caption,
                        "gender": p.gender or "",
                        "score": p.score,
                        # Fields legacy stylist expects but agent Product may not have — provide safe defaults
                        "wear_type": "",
                        "season": "",
                        "product_display_name": p.caption,
                    }
                    for p in products
                ]
                raw_result = _legacy_stylist.curate_outfits(
                    model_name=settings.stylist_model_name,
                    original_query="",  # agent does not pass original_query through this tool
                    products=products_as_dicts,
                    combo_count=settings.agent_max_results,
                    system_prompt=get_tool_prompt("stylist_system_prompt"),
                )
                rank = 1
                # Process top+bottom combos
                for raw_combo in (raw_result.get("combos") or []):
                    if rank > settings.agent_max_results:
                        break
                    combo = _to_outfit_combo_from_ids(raw_combo, rank, product_map)
                    if combo is not None:
                        combos.append(combo)
                        rank += 1
                # Process standalone full-body outfits
                for raw_solo in (raw_result.get("standalone_outfits") or []):
                    if rank > settings.agent_max_results:
                        break
                    combo = _to_outfit_combo_from_solo(raw_solo, rank, product_map)
                    if combo is not None:
                        combos.append(combo)
                        rank += 1
            except Exception as exc:
                entry["error"] = repr(exc)
                log.warning("curate_outfits failed, using fallback combos: %s", exc)
                # Fallback: zip top-3 products into individual single-item combos
                for rank, p in enumerate(products[:3], start=1):
                    combos.append(OutfitCombo(
                        combo_id=uuid.uuid4().hex[:12],
                        combo_rank=rank,
                        items=[p],
                        rationale="Stylist unavailable; showing raw results.",
                    ))

    # Emit child span with full combo data for LangSmith visibility.
    log.info("curate_outfits: produced %d combos from %d products", len(combos), len(products))
    _span_combo_results(combos=[c.model_dump() for c in combos])

    return Command(
        update={
            "messages": [
                ToolMessage(content=f"{len(combos)} combos curated", tool_call_id=tool_call_id)
            ],
            "last_combos": combos,
            "tool_trace": [ToolTraceEntry(**entry)],
        }
    )


def _to_outfit_combo_from_ids(
    raw_combo: dict,
    rank: int,
    product_map: dict[str, Product],
) -> OutfitCombo | None:
    """
    Create an outfit combination from referenced product identifiers.
    
    Parameters:
        raw_combo (dict): Combo data containing product identifiers and an optional styling rationale.
        rank (int): Rank assigned to the resulting outfit combination.
        product_map (dict[str, Product]): Products keyed by product identifier.
    
    Returns:
        OutfitCombo | None: The constructed combination, or None when no referenced products are found.
    """
    items: list[Product] = []
    for id_key in ("top_product_id", "bottom_product_id"):
        pid = raw_combo.get(id_key)
        if pid and pid in product_map:
            items.append(product_map[pid])
    if not items:
        return None
    rationale = str(
        raw_combo.get("styling_rationale")
        or raw_combo.get("rationale")
        or "Curated combo based on shared occasion and palette."
    ).strip() or "Curated combo based on shared occasion and palette."
    return OutfitCombo(
        combo_id=uuid.uuid4().hex[:12],
        combo_rank=rank,
        items=items,
        rationale=rationale,
    )


def _to_outfit_combo_from_solo(
    raw_solo: dict,
    rank: int,
    product_map: dict[str, Product],
) -> OutfitCombo | None:
    """Map a legacy standalone_outfit dict (product_id + rationale) to OutfitCombo.

    Returns None if the referenced product is not in product_map.
    """
    pid = raw_solo.get("product_id")
    if not pid or pid not in product_map:
        return None
    rationale = str(
        raw_solo.get("rationale")
        or raw_solo.get("styling_rationale")
        or "Curated combo based on shared occasion and palette."
    ).strip() or "Curated combo based on shared occasion and palette."
    return OutfitCombo(
        combo_id=uuid.uuid4().hex[:12],
        combo_rank=rank,
        items=[product_map[pid]],
        rationale=rationale,
    )
