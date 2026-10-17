from typing import Any

import httpx2
import pytest

from app.core.errors import (
    ServiceError,
    ServiceRateLimitedError,
    ServiceTimeoutError,
    ServiceUnavailableError,
)
from app.llm.fake_llm_client import FakeLLMClient
from tests.helpers import USAGE, ScriptedLLM, UseLLM, events

pytestmark = pytest.mark.anyio

QUESTION = {"messages": [{"role": "user", "content": "What is an LLM?"}]}
ANSWER = "Fake answer to: What is an LLM?"


async def test_chat_returns_the_whole_answer(client: httpx2.AsyncClient, use_llm: UseLLM) -> None:
    use_llm(FakeLLMClient())

    response = await client.post("/api/chat", json=QUESTION)

    assert response.status_code == httpx2.codes.OK
    body = response.json()
    assert body["content"] == ANSWER
    assert body["model"] == "fake"
    assert body["usage"]["completion_tokens"] == 7


async def test_chat_returns_the_reasoning_apart(
    client: httpx2.AsyncClient, use_llm: UseLLM
) -> None:
    use_llm(ScriptedLLM())

    body = (await client.post("/api/chat", json=QUESTION)).json()

    assert (body["reasoning"], body["content"]) == ("Greet.", "Hello")


async def test_messages_and_parameters_reach_the_model_as_given(
    client: httpx2.AsyncClient, use_llm: UseLLM
) -> None:
    llm = ScriptedLLM()
    use_llm(llm)
    parameters = {
        "temperature": 0.7,
        "seed": 42,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    image = {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}}
    message = {"role": "user", "content": [{"type": "text", "text": "What is this?"}, image]}

    await client.post("/api/chat", json={"messages": [message], "parameters": parameters})
    await client.post("/api/chat/stream", json={"messages": [message], "parameters": parameters})

    for messages, sent in llm.sent:
        assert [m.model_dump(exclude_none=True) for m in messages] == [message]
        assert sent == parameters


@pytest.mark.parametrize(
    "body",
    [
        {"messages": []},
        {"messages": [{"role": "tool", "content": "x"}]},
        {"messages": [{"role": "user", "content": ""}]},
        {**QUESTION, "parameters": {"model": "other"}},
        {**QUESTION, "parameters": {"stream": True}},
        {**QUESTION, "parameters": "hot"},
    ],
)
async def test_invalid_requests_are_refused(
    client: httpx2.AsyncClient, use_llm: UseLLM, body: dict[str, Any]
) -> None:
    use_llm(FakeLLMClient())

    for path in ("/api/chat", "/api/chat/stream"):
        response = await client.post(path, json=body)
        assert response.status_code == httpx2.codes.UNPROCESSABLE_CONTENT


async def test_a_reserved_parameter_is_named_in_the_refusal(
    client: httpx2.AsyncClient, use_llm: UseLLM
) -> None:
    use_llm(FakeLLMClient())

    response = await client.post("/api/chat", json={**QUESTION, "parameters": {"stream": True}})

    assert "the backend sets these itself: stream" in response.text


@pytest.mark.parametrize(
    ("error", "status_code"),
    [
        (ServiceTimeoutError("slow"), httpx2.codes.GATEWAY_TIMEOUT),
        (ServiceUnavailableError("down"), httpx2.codes.SERVICE_UNAVAILABLE),
        (ServiceRateLimitedError("busy"), httpx2.codes.TOO_MANY_REQUESTS),
        (ServiceError("odd"), httpx2.codes.BAD_GATEWAY),
    ],
)
async def test_llm_errors_become_http_errors(
    client: httpx2.AsyncClient, use_llm: UseLLM, error: ServiceError, status_code: int
) -> None:
    use_llm(ScriptedLLM(error))

    response = await client.post("/api/chat", json=QUESTION)

    assert response.status_code == status_code
    assert response.json() == {"detail": str(error)}


async def test_stream_sends_reasoning_then_tokens_then_done(
    client: httpx2.AsyncClient, use_llm: UseLLM
) -> None:
    use_llm(ScriptedLLM())

    response = await client.post("/api/chat/stream", json=QUESTION)

    assert response.status_code == httpx2.codes.OK
    assert response.headers["content-type"].startswith("text/event-stream")
    assert events(response.text) == [
        ("reasoning", {"text": "Greet."}),
        ("token", {"text": "Hel"}),
        ("token", {"text": "lo"}),
        ("done", {"model": "scripted", "finish_reason": "stop", "usage": USAGE}),
    ]


async def test_stream_sets_proxy_friendly_headers(
    client: httpx2.AsyncClient, use_llm: UseLLM
) -> None:
    use_llm(FakeLLMClient())

    response = await client.post("/api/chat/stream", json=QUESTION)

    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["x-accel-buffering"] == "no"


async def test_stream_failures_end_with_an_error_event(
    client: httpx2.AsyncClient, use_llm: UseLLM
) -> None:
    use_llm(ScriptedLLM(ServiceUnavailableError("down"), pieces_first=2))

    response = await client.post("/api/chat/stream", json=QUESTION)

    assert events(response.text) == [
        ("reasoning", {"text": "Greet."}),
        ("token", {"text": "Hel"}),
        ("error", {"status": 503, "detail": "down"}),
    ]


@pytest.mark.parametrize(
    ("error", "status_code"),
    [
        (ServiceTimeoutError("slow"), 504),
        (ServiceUnavailableError("down"), 503),
        (ServiceRateLimitedError("busy"), 429),
        (ServiceError("odd"), 502),
    ],
)
async def test_a_stream_error_carries_the_status_the_request_answers_without_streaming(
    client: httpx2.AsyncClient, use_llm: UseLLM, error: ServiceError, status_code: int
) -> None:
    use_llm(ScriptedLLM(error, pieces_first=1))

    streamed = await client.post("/api/chat/stream", json=QUESTION)
    answered = await client.post("/api/chat", json=QUESTION)

    assert events(streamed.text)[-1] == ("error", {"status": status_code, "detail": str(error)})
    assert answered.status_code == status_code
