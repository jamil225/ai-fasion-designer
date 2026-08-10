import logging
import time

import litellm

from src.config import Settings
from src.schemas import LiteLLMTestRequest, LiteLLMTestResponse

logger = logging.getLogger(__name__)


def run_litellm_test(settings: Settings, request: LiteLLMTestRequest) -> LiteLLMTestResponse:
    start = time.monotonic()
    response = litellm.completion(
        model=settings.litellm_test_model_name,
        messages=[{"role": "user", "content": request.prompt}],
        vertex_project=settings.google_cloud_project,
        vertex_location=settings.google_cloud_location,
    )
    latency_ms = int((time.monotonic() - start) * 1000)

    text = response.choices[0].message.content
    logger.info(
        "litellm-test call OK — model=%s latency_ms=%d",
        settings.litellm_test_model_name,
        latency_ms,
    )
    return LiteLLMTestResponse(
        text=text,
        model=settings.litellm_test_model_name,
        latency_ms=latency_ms,
    )
