"""The /api/llm endpoints, which any page that talks to the model uses."""

import httpx2
import pytest

from app.core.errors import ServiceUnavailableError
from app.llm.fake_llm_client import FakeLLMClient
from tests.helpers import ScriptedLLM, UseLLM

pytestmark = pytest.mark.anyio


async def test_model_tells_the_model_and_its_inputs(
    client: httpx2.AsyncClient, use_llm: UseLLM
) -> None:
    use_llm(FakeLLMClient())

    response = await client.get("/api/llm/model")

    assert response.status_code == httpx2.codes.OK
    assert response.json() == {"model": "fake", "inputs": ["text", "image", "audio", "video"]}


async def test_model_answers_the_llms_errors_as_http_errors(
    client: httpx2.AsyncClient, use_llm: UseLLM
) -> None:
    use_llm(ScriptedLLM(ServiceUnavailableError("The LLM endpoint can't be reached.")))

    response = await client.get("/api/llm/model")

    assert response.status_code == httpx2.codes.SERVICE_UNAVAILABLE
