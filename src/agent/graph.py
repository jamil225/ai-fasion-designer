from __future__ import annotations

import logging

from langchain_google_genai import ChatGoogleGenerativeAI
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

log = logging.getLogger(__name__)
_settings = Settings()

_LLM = ChatGoogleGenerativeAI(
    model=_settings.agent_model_name,
    google_api_key=_settings.gemini_api_key,
    temperature=0,
)

_CHECKPOINTER = InMemorySaver()

_AGENT = create_react_agent(
    model=_LLM,
    tools=[check_required_fields, ask_user, enrich_query, search_products, curate_outfits],
    state_schema=FashionAgentState,
    checkpointer=_CHECKPOINTER,
    prompt=get_agent_prompt("agent_system_prompt"),
)

# Apply recursion cap globally so callers don't have to remember it.
AGENT = _AGENT.with_config({"recursion_limit": _settings.agent_recursion_limit})
