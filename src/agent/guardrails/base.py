from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Optional


class GuardrailResult(BaseModel):
    passed: bool
    reason: Optional[str] = None


class BaseGuardrail(ABC):
    @abstractmethod
    async def validate(self, context: dict) -> GuardrailResult:
        pass
