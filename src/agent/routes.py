from __future__ import annotations

import logging
import time
import uuid
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.errors import GraphRecursionError
from langgraph.types import Command

from src.agent.graph import AGENT
from src.auth import verify_auth
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

log = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/chat", tags=["chat"])


def _detect_interrupt(thread_id: str) -> Optional[dict]:
    """Return the payload of the first pending interrupt for this thread, or None."""
    state = AGENT.get_state(config={"configurable": {"thread_id": thread_id}})
    if not state or not state.tasks:
        return None
    for task in state.tasks:
        for itr in getattr(task, "interrupts", ()) or ():
            return itr.value
    return None


def _read_state_values(thread_id: str) -> dict:
    state = AGENT.get_state(config={"configurable": {"thread_id": thread_id}})
    return dict(state.values) if state and state.values else {}


def _final_message_text(state_values: dict) -> str:
    msgs = state_values.get("messages") or []
    for msg in reversed(msgs):
        if isinstance(msg, AIMessage) and not getattr(msg, "tool_calls", None):
            return msg.content if isinstance(msg.content, str) else str(msg.content)
    return ""


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
            # v3.0: only 'respond' decisions; take the first.
            first = req.resume.decisions[0]
            if first.type != "respond":
                raise HTTPException(status_code=400, detail="only 'respond' decisions are supported in v3.0.")
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
    state_values = _read_state_values(thread_id)
    turn_count = int(state_values.get("turn_count") or 0)

    pending = _detect_interrupt(thread_id)
    if pending:
        return ChatInterruptResponse(
            thread_id=thread_id,
            request_id=request_id,
            turn_count=turn_count,
            pending_action=PendingAction(
                name=pending.get("type", "ask_user") if isinstance(pending, dict) else "ask_user",
                arguments={"question": pending.get("question") if isinstance(pending, dict) else str(pending)},
            ),
            latency_ms=latency_ms,
        ).model_dump()

    combos = [c if isinstance(c, OutfitCombo) else OutfitCombo(**c) for c in (state_values.get("last_combos") or [])]
    applied_filters = state_values.get("current_filters")
    if applied_filters is not None and not isinstance(applied_filters, SearchFilters):
        applied_filters = SearchFilters(**applied_filters)
    tool_trace = [t if isinstance(t, ToolTraceEntry) else ToolTraceEntry(**t) for t in (state_values.get("tool_trace") or [])]

    return ChatFinalResponse(
        thread_id=thread_id,
        request_id=request_id,
        turn_count=turn_count,
        message=_final_message_text(state_values),
        combos=combos,
        applied_slots=dict(state_values.get("gathered_slots") or {}),
        applied_filters=applied_filters,
        latency_ms=latency_ms,
        tool_trace=tool_trace,
    ).model_dump()


# ---------------------------------------------------------------------------
# Task 5.2 — GET /v1/chat/threads/{thread_id}  (PRD §Public APIs)
# ---------------------------------------------------------------------------

def _extract_pending_action(state) -> Optional[PendingAction]:
    """Return PendingAction from state.tasks if the thread is interrupted, else None."""
    if not state or not state.tasks:
        return None
    for task in state.tasks:
        for itr in getattr(task, "interrupts", ()) or ():
            payload = itr.value
            if isinstance(payload, dict):
                question = payload.get("question", "")
                name = payload.get("type", "ask_user")
            else:
                question = str(payload)
                name = "ask_user"
            return PendingAction(name=name, arguments={"question": question})
    return None


def _serialize_messages(state_values: dict) -> list[dict]:
    """Return messages as [{role, content}], stripping tool internals."""
    out: list[dict] = []
    for msg in state_values.get("messages") or []:
        if isinstance(msg, HumanMessage):
            text = msg.content if isinstance(msg.content, str) else str(msg.content)
            out.append({"role": "user", "content": text})
        elif isinstance(msg, AIMessage):
            # Skip pure tool-call nodes (no visible text)
            if getattr(msg, "tool_calls", None) and not msg.content:
                continue
            text = msg.content if isinstance(msg.content, str) else str(msg.content)
            out.append({"role": "assistant", "content": text})
        elif isinstance(msg, SystemMessage):
            continue  # omit system messages from public response
    return out


@router.get("/threads/{thread_id}", dependencies=[Depends(verify_auth)])
async def get_thread(thread_id: str) -> dict:
    """Inspect the current state of a chat thread (diagnostic endpoint)."""
    state = AGENT.get_state(config={"configurable": {"thread_id": thread_id}})
    if not state or not state.values:
        raise HTTPException(status_code=404, detail="Thread not found.")

    state_values = dict(state.values)
    messages = _serialize_messages(state_values)
    pending = _extract_pending_action(state)

    return {
        "thread_id": thread_id,
        "messages": messages,
        "pending_action": pending.model_dump() if pending else None,
        "turn_count": int(state_values.get("turn_count") or 0),
        "gathered_slots": dict(state_values.get("gathered_slots") or {}),
    }
