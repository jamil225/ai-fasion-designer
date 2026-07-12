from __future__ import annotations

import logging

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import create_react_agent

from src.agent.prompt_loader import get_agent_prompt
from src.agent.schemas import FashionAgentState
from src.agent.tools import (
    ask_user,
    check_required_fields,
    curate_outfits,
    enrich_query,
    search_products,
)
from src.config import Settings
from src.llm_gateway import get_chat_model

log = logging.getLogger(__name__)
_settings = Settings()

# Chat model comes through the gateway so the agent's provider is swappable in one place.
# (Currently the gateway serves a Vertex chat model; LiteLLM chat-model support is deferred.)
_LLM = get_chat_model(
    task="agent",
    model=_settings.agent_model_name,
    temperature=0,
)
log.info("Agent LLM loaded: model=%s", _settings.agent_model_name)

_CHECKPOINTER = InMemorySaver()
log.info("Agent checkpointer: %s", type(_CHECKPOINTER).__name__)

_AGENT = create_react_agent(
    model=_LLM,
    tools=[check_required_fields, ask_user, enrich_query, search_products, curate_outfits],
    state_schema=FashionAgentState,
    checkpointer=_CHECKPOINTER,
    prompt=get_agent_prompt("agent_system_prompt"),
    name="fashion-stylist-agent",
)

# Apply recursion cap globally so callers don't have to remember it.
AGENT = _AGENT.with_config({"recursion_limit": _settings.agent_recursion_limit})
log.info("ReAct agent ready: name=fashion-stylist-agent, tools=5, recursion_limit=%d", _settings.agent_recursion_limit)
