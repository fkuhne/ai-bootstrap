"""Builds the LLM client the settings ask for (Factory)."""

import httpx2
from openai import AsyncOpenAI

from app.llm.config import LLMSettings
from app.llm.fake_llm_client import FakeLLMClient
from app.llm.llm_client import LLMClient
from app.llm.openai_compatible_client import OpenAICompatibleClient


def create_llm_client(
    settings: LLMSettings, *, http_client: httpx2.AsyncClient | None = None
) -> LLMClient:
    """Return the client for `settings.provider`.

    Tests pass an `http_client` with a mock transport, so no request leaves the process. The
    OpenAI SDK runs on httpx2, so that client comes from httpx2.
    """
    if settings.provider == "fake":
        return FakeLLMClient()
    sdk = AsyncOpenAI(
        base_url=str(settings.base_url),
        api_key=settings.api_key.get_secret_value(),
        timeout=settings.timeout_seconds,
        # Off: the SDK retries timeouts too. The client retries by its own rule.
        max_retries=0,
        http_client=http_client,
    )
    return OpenAICompatibleClient(
        sdk, model=settings.model, inputs=settings.inputs, max_retries=settings.max_retries
    )
