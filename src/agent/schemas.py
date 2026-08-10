from __future__ import annotations

import operator
from typing import Annotated, NotRequired

from pydantic import BaseModel, Field
from langgraph.prebuilt.chat_agent_executor import AgentState


class ToolTraceEntry(BaseModel):
    tool_name: str
    latency_ms: int
    error: str | None = None


class SlotCheckResult(BaseModel):
    all_filled: bool
    missing_fields: list[str]
    gathered_slots: dict[str, str]


class SearchFilters(BaseModel):
    colors: list[str] | None = None
    occasion: str | None = None
    category: list[str] | None = None
    gender: str | None = None


class EnrichedQuery(BaseModel):
    semantic_query: str
    inferred_colors: list[str]
    inferred_category: list[str]
    reasoning: str


class Product(BaseModel):
    product_id: str
    image_path: str
    score: float
    category: str
    colors: list[str]
    occasion: str
    style_tags: list[str]
    caption: str
    gender: str | None = None


class OutfitCombo(BaseModel):
    combo_id: str
    combo_rank: int
    items: list[Product]
    rationale: str


# ----- API request/response shapes (PRD §Public APIs) -----

class ChatRequest(BaseModel):
    thread_id: str
    message: str


class ChatResumeDecision(BaseModel):
    type: str
    message: str


class ChatResumeBody(BaseModel):
    decisions: list[ChatResumeDecision]


class ChatResumeRequest(BaseModel):
    thread_id: str
    resume: ChatResumeBody


class PendingAction(BaseModel):
    name: str
    arguments: dict


class ChatFinalResponse(BaseModel):
    type: str = "final"
    thread_id: str
    request_id: str
    turn_count: int
    message: str
    combos: list[OutfitCombo]
    applied_slots: dict[str, str]
    applied_filters: SearchFilters | None = None
    latency_ms: int
    tool_trace: list[ToolTraceEntry]
    guardrails_passed: bool = True


class ChatInterruptResponse(BaseModel):
    type: str = "interrupt"
    thread_id: str
    request_id: str
    turn_count: int
    pending_action: PendingAction
    latency_ms: int
    guardrails_passed: bool = True


# ----- Agent state (PRD §State) -----
# AgentState is a TypedDict (subclass of dict). Fields that may be absent at
# graph init are declared NotRequired so they can be omitted from the initial
# state dict without a KeyError. tool_trace uses operator.add as a reducer so
# concurrent tool writes append rather than overwrite.


def _merge_slot_dict(existing: dict[str, str] | None, new: dict[str, str]) -> dict[str, str]:
    """
    Merge newly gathered slot values into existing values.
    
    Parameters:
        existing (dict[str, str] | None): Previously gathered slot values.
        new (dict[str, str]): Newly gathered slot values.
    
    Returns:
        dict[str, str]: Combined slot values, with new values taking precedence.
    """
    return {**(existing or {}), **(new or {})}


class FashionAgentState(AgentState):
    gathered_slots: Annotated[dict[str, str], _merge_slot_dict]
    current_filters: NotRequired[SearchFilters | None]
    last_semantic_query: NotRequired[str | None]
    last_products: list[Product]
    last_combos: list[OutfitCombo]
    turn_count: int
    request_id: NotRequired[str | None]
    tool_trace: Annotated[list[ToolTraceEntry], operator.add]
