from functools import lru_cache
from pathlib import Path

import yaml

_PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"


@lru_cache(maxsize=2)
def _load(file_name: str) -> dict[str, str]:
    return yaml.safe_load((_PROMPTS_DIR / file_name).read_text())


def get_agent_prompt(key: str) -> str:
    return _load("agent_prompts.yaml")[key]


def get_tool_prompt(key: str) -> str:
    return _load("tool_prompts.yaml")[key]
