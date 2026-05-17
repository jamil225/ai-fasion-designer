from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Annotated, Any, Iterator

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool, InjectedToolCallId  # InjectedToolCallId lives in langchain_core.tools (not langgraph)
from langgraph.prebuilt import InjectedState              # InjectedState lives in langgraph.prebuilt
from langgraph.types import Command

from src.agent.schemas import SlotCheckResult, ToolTraceEntry
from src.config import Settings

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
