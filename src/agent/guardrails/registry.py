import logging
from typing import List
from src.config import GuardrailsConfig
from .base import BaseGuardrail, GuardrailResult

logger = logging.getLogger(__name__)


class GuardrailRegistry:
    def __init__(self, config: GuardrailsConfig):
        self.config = config
        self.input_guardrails: List[BaseGuardrail] = []
        self.output_guardrails: List[BaseGuardrail] = []
        logger.info("GuardrailRegistry initialized (master=%s, input=%s, output=%s)",
                     config.enabled, config.input.enabled, config.output.enabled)

    def register_input_guardrail(self, guardrail: BaseGuardrail) -> None:
        self.input_guardrails.append(guardrail)
        logger.info("Registered input guardrail: %s", type(guardrail).__name__)

    def register_output_guardrail(self, guardrail: BaseGuardrail) -> None:
        self.output_guardrails.append(guardrail)
        logger.info("Registered output guardrail: %s", type(guardrail).__name__)

    async def run_input_guardrails(self, request_body: str) -> GuardrailResult:
        if not self.config.enabled or not self.config.input.enabled:
            logger.info("Input guardrails BYPASSED (disabled by config)")
            return GuardrailResult(passed=True)
            
        context = {"text": request_body}
        
        for guardrail in self.input_guardrails:
            result = await guardrail.validate(context)
            if not result.passed:
                logger.info("Input guardrail REJECTED by %s: %s", type(guardrail).__name__, result.reason)
                return result
                
        logger.info("Input guardrails PASSED (%d checks)", len(self.input_guardrails))
        return GuardrailResult(passed=True)

