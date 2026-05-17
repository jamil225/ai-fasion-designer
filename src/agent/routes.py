from __future__ import annotations

import logging
import time
import uuid
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.errors import GraphRecursionError
from langgraph.types import Command

from src.agent.graph import AGENT
from src.agent.schemas import (
    ChatFinalResponse,
    ChatInterruptResponse,
    ChatRequest,
    ChatResumeRequest,
    OutfitCombo,
    PendingAction,
    SearchFilters,
    ToolTraceEntry,
)
from src.auth import verify_auth

log = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/chat", tags=["chat"])


# ---------------------------------------------------------------------------
# Helpers — read graph state + detect pending interrupts (v0.3 langgraph)
# ---------------------------------------------------------------------------

def _read_state(thread_id: str) -> dict:
    state = AGENT.get_state(config={"configurable": {"thread_id": thread_id}})
    return dict(state.values) if state and state.values else {}


def _detect_interrupt(thread_id: str) -> Optional[dict]:
    state = AGENT.get_state(config={"configurable": {"thread_id": thread_id}})
    if not state or not state.tasks:
        return None
    for task in state.tasks:
        for itr in getattr(task, "interrupts", ()) or ():
            return itr.value
    return None


def _final_text(state_values: dict) -> str:
    for msg in reversed(state_values.get("messages") or []):
        if isinstance(msg, AIMessage) and not getattr(msg, "tool_calls", None):
            return msg.content if isinstance(msg.content, str) else str(msg.content)
    return ""


# ---------------------------------------------------------------------------
# POST /v1/chat — thin agent invoker (PRD §Public APIs)
# ---------------------------------------------------------------------------

@router.post("", dependencies=[Depends(verify_auth)])
async def chat(body: dict = Body(...)) -> dict:
    request_id = uuid.uuid4().hex
    start = time.perf_counter()

    has_message = "message" in body and body["message"] is not None
    has_resume = "resume" in body and body["resume"] is not None
    if has_message == has_resume:
        raise HTTPException(status_code=400, detail="Provide exactly one of 'message' or 'resume'.")

    thread_id = body.get("thread_id")
    if not thread_id or not isinstance(thread_id, str):
        raise HTTPException(status_code=400, detail="thread_id is required.")

    config = {"configurable": {"thread_id": thread_id}}
    trace_before = len(_read_state(thread_id).get("tool_trace") or [])

    try:
        if has_message:
            req = ChatRequest(thread_id=thread_id, message=body["message"])
            if len(req.message) > 500:
                raise HTTPException(status_code=400, detail="message must be <= 500 characters.")
            AGENT.invoke({"messages": [HumanMessage(content=req.message)]}, config=config)
        else:
            req = ChatResumeRequest(thread_id=thread_id, resume=body["resume"])
            if not req.resume.decisions:
                raise HTTPException(status_code=400, detail="resume.decisions must be non-empty.")
            first = req.resume.decisions[0]
            if first.type != "respond":
                raise HTTPException(status_code=400, detail="only 'respond' decisions are supported in v3.0.")
            if _detect_interrupt(thread_id) is None:
                raise HTTPException(
                    status_code=409,
                    detail="No pending interrupt for this thread (server may have restarted). Start a new thread.",
                )
            AGENT.invoke(Command(resume=first.message), config=config)
    except GraphRecursionError as exc:
        log.warning("recursion limit hit on thread %s: %s", thread_id, exc)
        raise HTTPException(status_code=500, detail="Agent took too many steps. Please start a new thread.") from exc
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("agent invoke failed on thread %s", thread_id)
        raise HTTPException(status_code=500, detail=f"agent error: {exc!r}") from exc

    latency_ms = int((time.perf_counter() - start) * 1000)
    sv = _read_state(thread_id)
    turn_count = int(sv.get("turn_count") or 0)

    pending = _detect_interrupt(thread_id)
    if pending:
        question = pending.get("question") if isinstance(pending, dict) else str(pending)
        name = pending.get("type", "ask_user") if isinstance(pending, dict) else "ask_user"
        return ChatInterruptResponse(
            thread_id=thread_id,
            request_id=request_id,
            turn_count=turn_count,
            pending_action=PendingAction(name=name, arguments={"question": question}),
            latency_ms=latency_ms,
        ).model_dump()

    af = sv.get("current_filters")
    if af is not None and not isinstance(af, SearchFilters):
        af = SearchFilters(**af)
    all_trace = [t if isinstance(t, ToolTraceEntry) else ToolTraceEntry(**t) for t in (sv.get("tool_trace") or [])]
    trace = all_trace[trace_before:]
    produced_combos = any(t.tool_name == "curate_outfits" for t in trace)
    combos = (
        [c if isinstance(c, OutfitCombo) else OutfitCombo(**c) for c in (sv.get("last_combos") or [])]
        if produced_combos else []
    )

    return ChatFinalResponse(
        thread_id=thread_id,
        request_id=request_id,
        turn_count=turn_count,
        message=_final_text(sv),
        combos=combos,
        applied_slots=dict(sv.get("gathered_slots") or {}),
        applied_filters=af,
        latency_ms=latency_ms,
        tool_trace=trace,
    ).model_dump()


# ---------------------------------------------------------------------------
# GET /v1/chat/threads/{thread_id} — diagnostic (Task 5.2, PRD §Public APIs)
# ---------------------------------------------------------------------------

def _extract_pending(state) -> Optional[PendingAction]:
    if not state or not state.tasks:
        return None
    for task in state.tasks:
        for itr in getattr(task, "interrupts", ()) or ():
            payload = itr.value
            question = payload.get("question", "") if isinstance(payload, dict) else str(payload)
            name = payload.get("type", "ask_user") if isinstance(payload, dict) else "ask_user"
            return PendingAction(name=name, arguments={"question": question})
    return None


def _serialize_messages(state_values: dict) -> list[dict]:
    out: list[dict] = []
    for msg in state_values.get("messages") or []:
        if isinstance(msg, HumanMessage):
            text = msg.content if isinstance(msg.content, str) else str(msg.content)
            out.append({"role": "user", "content": text})
        elif isinstance(msg, AIMessage):
            if getattr(msg, "tool_calls", None) and not msg.content:
                continue
            text = msg.content if isinstance(msg.content, str) else str(msg.content)
            out.append({"role": "assistant", "content": text})
    return out


@router.get("/threads/{thread_id}", dependencies=[Depends(verify_auth)])
async def get_thread(thread_id: str) -> dict:
    state = AGENT.get_state(config={"configurable": {"thread_id": thread_id}})
    if not state or not state.values:
        raise HTTPException(status_code=404, detail="Thread not found.")

    sv = dict(state.values)
    pending = _extract_pending(state)
    return {
        "thread_id": thread_id,
        "messages": _serialize_messages(sv),
        "pending_action": pending.model_dump() if pending else None,
        "turn_count": int(sv.get("turn_count") or 0),
        "gathered_slots": dict(sv.get("gathered_slots") or {}),
        "tool_trace": [
            (t if isinstance(t, ToolTraceEntry) else ToolTraceEntry(**t)).model_dump()
            for t in (sv.get("tool_trace") or [])
        ],
    }
