import json

import httpx2
import pytest
from fastapi import FastAPI
from pydantic import HttpUrl, SecretStr
from starlette.requests import Request

from app.core.errors import ServiceUnavailableError
from app.llm.config import LLMSettings
from app.llm.dependencies import get_llm_client
from app.llm.factory import create_llm_client
from app.llm.fake_llm_client import FakeLLMClient
from app.llm.llm_client import ChatMessage
from app.llm.openai_compatible_client import OpenAICompatibleClient

pytestmark = pytest.mark.anyio


async def test_the_fake_provider_builds_the_fake_client() -> None:
    client = create_llm_client(LLMSettings(provider="fake"))

    assert isinstance(client, FakeLLMClient)


async def test_the_openai_compatible_provider_uses_the_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def no_wait(_seconds: float) -> None:
        return None

    monkeypatch.setattr("app.llm.openai_compatible_client.asyncio.sleep", no_wait)
    requests: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return httpx2.Response(503)

    settings = LLMSettings(
        base_url=HttpUrl("http://llm.test/v1"),
        api_key=SecretStr("k1"),
        model="m1",
        max_retries=1,
    )
    http = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))

    client = create_llm_client(settings, http_client=http)
    await client.is_ready()
    with pytest.raises(ServiceUnavailableError, match="503"):
        await client.complete([ChatMessage(role="user", content="Hi")])

    assert isinstance(client, OpenAICompatibleClient)
    # Readiness once; the completion once, then retried once: the client's retries, not the SDK's.
    assert len(requests) == 3
    assert str(requests[0].url) == "http://llm.test/v1/chat/completions"
    assert requests[0].headers["authorization"] == "Bearer k1"
    assert json.loads(requests[1].content)["model"] == "m1"


async def test_the_dependency_returns_the_client_the_lifespan_created() -> None:
    app = FastAPI()
    app.state.llm_client = FakeLLMClient()

    client = await get_llm_client(Request({"type": "http", "app": app}))

    assert client is app.state.llm_client


async def test_the_configured_inputs_reach_the_client() -> None:
    client = create_llm_client(LLMSettings(model="m1", inputs=["text", "image"]))

    info = await client.model_info()

    assert (info.model, info.inputs) == ("m1", ["text", "image"])
    await client.aclose()
