from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Optional


class GuardrailResult(BaseModel):
    passed: bool
    reason: Optional[str] = None


class BaseGuardrail(ABC):
    @abstractmethod
    async def validate(self, context: dict) -> GuardrailResult:
        """
        Validate the supplied context against the guardrail's criteria.
        
        Parameters:
        	context (dict): Context data to validate.
        
        Returns:
        	GuardrailResult: The validation outcome and optional explanation.
        """
        pass
