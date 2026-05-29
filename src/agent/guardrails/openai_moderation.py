import logging
import time

from openai import AsyncOpenAI
from src.config import get_settings
from .base import BaseGuardrail, GuardrailResult

logger = logging.getLogger(__name__)


class OpenAIModerationGuardrail(BaseGuardrail):
    def __init__(self):
        settings = get_settings()
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def validate(self, context: dict) -> GuardrailResult:
        text = context.get("text", "")
        if not text:
            return GuardrailResult(passed=True)

        try:
            _start = time.perf_counter()
            response = await self.client.moderations.create(input=text)
            _latency_ms = int((time.perf_counter() - _start) * 1000)
            
            if not response.results:
                return GuardrailResult(passed=True)
                
            result = response.results[0]
            
            if result.flagged:
                flagged_categories = [
                    cat for cat, is_flagged in result.categories.model_dump().items() if is_flagged
                ]
                logger.warning(
                    f"Safety violation detected. Input: '{text}'. Categories: {flagged_categories}"
                )
                return GuardrailResult(
                    passed=False, 
                    reason="Input violated safety policies."
                )
                
            logger.info("OpenAI moderation PASSED (%dms)", _latency_ms)
            return GuardrailResult(passed=True)
            
        except Exception as e:
            logger.exception("OpenAI Moderation API call failed")
            # Fail-closed
            return GuardrailResult(
                passed=False, 
                reason="Safety check temporarily unavailable."
            )
