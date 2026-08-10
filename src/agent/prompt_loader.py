from functools import lru_cache
from pathlib import Path

import yaml

_PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"


@lru_cache(maxsize=2)
def _load(file_name: str) -> dict[str, str]:
    """Load a prompt mapping from a YAML file.
    
    Parameters:
        file_name (str): Name of the YAML file in the prompts directory.
    
    Returns:
        dict[str, str]: Parsed prompt mapping.
    """
    return yaml.safe_load((_PROMPTS_DIR / file_name).read_text())


def get_agent_prompt(key: str) -> str:
    """Retrieve an agent prompt by its key.
    
    Parameters:
        key (str): Identifier of the prompt to retrieve.
    
    Returns:
        str: The prompt text associated with the key.
    """
    return _load("agent_prompts.yaml")[key]


def get_tool_prompt(key: str) -> str:
    """Retrieve a tool prompt by its key.
    
    Parameters:
        key (str): The key identifying the tool prompt.
    
    Returns:
        str: The tool prompt associated with the key.
    """
    return _load("tool_prompts.yaml")[key]
