"""The adapter talks to a mock transport: real SDK, real HTTP parsing, no network."""

import json
from collections.abc import Callable

import httpx2
import openai
import pytest
from openai import AsyncOpenAI

from app.core.errors import (
    ServiceError,
    ServiceRateLimitedError,
    ServiceTimeoutError,
    ServiceUnavailableError,
)
from app.core.services import READINESS_TIMEOUT_SECONDS
from app.llm.llm_client import (
    AudioPart,
    ChatMessage,
    Completion,
    ContentDelta,
    ImagePart,
    ImageURL,
    Media,
    ModelInfo,
    Parameters,
    ReasoningDelta,
    StreamEnd,
    StreamPart,
    TextPart,
    Usage,
    VideoPart,
)
from app.llm.openai_compatible_client import SERVICE, OpenAICompatibleClient
from app.llm.openai_errors import translate

pytestmark = pytest.mark.anyio

Handler = Callable[[httpx2.Request], httpx2.Response]
MESSAGES = [ChatMessage(role="user", content="Hello?")]
USAGE = {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5}


def make_client(
    handler: Handler,
    http: httpx2.AsyncClient | None = None,
    *,
    retries: int = 0,
    retry_delay_seconds: float = 0.0,
) -> OpenAICompatibleClient:
    http = http or httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    sdk = AsyncOpenAI(
        base_url="http://llm.test/v1", api_key="test", max_retries=0, http_client=http
    )
    return OpenAICompatibleClient(
        sdk, model="test-model", max_retries=retries, retry_delay_seconds=retry_delay_seconds
    )


def completion_body(
    content: str | None, *, usage: bool = True, message: dict[str, object] | None = None
) -> dict[str, object]:
    body: dict[str, object] = {
        "id": "cmpl-1",
        "object": "chat.completion",
        "created": 0,
        "model": "served-model",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content, **(message or {})},
                "finish_reason": "stop",
            }
        ],
    }
    if usage:
        body["usage"] = USAGE
    return body


def chunk(
    content: str | None = None, *, finish_reason: str | None = None, **delta_fields: object
) -> dict[str, object]:
    delta = {"content": content, **delta_fields} if content or delta_fields else {}
    return {
        "id": "cmpl-1",
        "object": "chat.completion.chunk",
        "created": 0,
        "model": "served-model",
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
    }


def usage_chunk() -> dict[str, object]:
    """The last chunk when the usage is asked for: no choices, only the usage."""
    return {**chunk(), "choices": [], "usage": USAGE}


def sse(*events: dict[str, object] | str) -> bytes:
    lines = (f"data: {e if isinstance(e, str) else json.dumps(e)}\n\n" for e in events)
    return "".join(lines).encode()


def streamed(*events: dict[str, object] | str) -> httpx2.Response:
    return httpx2.Response(200, headers={"content-type": "text/event-stream"}, content=sse(*events))


class Recorder:
    """A mock-transport handler that answers `response` and keeps every request."""

    def __init__(self, response: httpx2.Response) -> None:
        self.response = response
        self.requests: list[httpx2.Request] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        return self.response

    @property
    def payload(self) -> dict[str, object]:
        body: dict[str, object] = json.loads(self.requests[-1].content)
        return body


async def collect(client: OpenAICompatibleClient) -> list[StreamPart]:
    return [part async for part in client.stream(MESSAGES)]


async def test_complete_returns_the_answer_and_its_usage() -> None:
    recorder = Recorder(httpx2.Response(200, json=completion_body("Hi!")))

    completion = await make_client(recorder).complete(MESSAGES)

    assert completion == Completion(
        content="Hi!", model="served-model", finish_reason="stop", usage=Usage(**USAGE)
    )
    assert recorder.requests[-1].url.path == "/v1/chat/completions"
    assert recorder.payload == {
        "model": "test-model",
        "messages": [{"role": "user", "content": "Hello?"}],
    }


async def test_parameters_pass_through_as_given_and_none_are_added() -> None:
    recorder = Recorder(httpx2.Response(200, json=completion_body("Hi!")))
    parameters: Parameters = {
        "temperature": 0.7,
        "seed": 42,
        "reasoning_effort": "low",
        "chat_template_kwargs": {"enable_thinking": False},
        "verbosity": "low",
    }

    await make_client(recorder).complete(MESSAGES, parameters=parameters)

    assert recorder.payload == {
        "model": "test-model",
        "messages": [{"role": "user", "content": "Hello?"}],
        **parameters,
    }


async def test_images_audio_and_video_are_sent_as_content_parts() -> None:
    recorder = Recorder(httpx2.Response(200, json=completion_body("A red square.")))
    message = ChatMessage(
        role="user",
        content=[
            TextPart(text="What do you see and hear?"),
            ImagePart(image_url=ImageURL(url="data:image/png;base64,AAAA")),
            AudioPart(input_audio=Media(data="UklGRg==", format="wav")),
            VideoPart(input_video=Media(url="https://example.com/clip.mp4")),
        ],
    )

    await make_client(recorder).complete([message])

    assert recorder.payload["messages"] == [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "What do you see and hear?"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}},
                {"type": "input_audio", "input_audio": {"data": "UklGRg==", "format": "wav"}},
                {"type": "input_video", "input_video": {"url": "https://example.com/clip.mp4"}},
            ],
        }
    ]


@pytest.mark.parametrize("field", ["reasoning_content", "reasoning"])
async def test_the_reasoning_comes_back_whichever_field_the_server_uses(field: str) -> None:
    recorder = Recorder(
        httpx2.Response(200, json=completion_body("4", message={field: "2 + 2 = 4"}))
    )

    completion = await make_client(recorder).complete(MESSAGES)

    assert (completion.content, completion.reasoning) == ("4", "2 + 2 = 4")


async def test_a_missing_content_reasoning_or_usage_is_tolerated() -> None:
    recorder = Recorder(httpx2.Response(200, json=completion_body(None, usage=False)))

    completion = await make_client(recorder).complete(MESSAGES)

    assert (completion.content, completion.reasoning, completion.usage) == ("", None, None)


async def test_stream_yields_reasoning_then_text_then_the_end() -> None:
    recorder = Recorder(
        streamed(
            chunk(),
            chunk(reasoning_content="Two words"),
            chunk(reasoning_content="."),
            chunk("Hel"),
            chunk("lo", finish_reason="stop"),
            usage_chunk(),
            "[DONE]",
        )
    )

    parts = await collect(make_client(recorder))

    assert parts == [
        ReasoningDelta(text="Two words"),
        ReasoningDelta(text="."),
        ContentDelta(text="Hel"),
        ContentDelta(text="lo"),
        StreamEnd(model="served-model", finish_reason="stop", usage=Usage(**USAGE)),
    ]
    assert recorder.payload["stream"] is True
    assert recorder.payload["stream_options"] == {"include_usage": True}


async def test_a_stream_without_usage_still_ends() -> None:
    recorder = Recorder(streamed(chunk("Hi", finish_reason="length"), "[DONE]"))

    parts = await collect(make_client(recorder))

    assert parts[-1] == StreamEnd(model="served-model", finish_reason="length", usage=None)


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (503, ServiceUnavailableError),
        (500, ServiceError),
        (429, ServiceRateLimitedError),
        (400, ServiceError),
    ],
)
async def test_http_errors_become_domain_errors(status: int, error: type[ServiceError]) -> None:
    client = make_client(Recorder(httpx2.Response(status, json={"error": {"message": "no"}})))

    with pytest.raises(error) as raised:
        await client.complete(MESSAGES)

    assert type(raised.value) is error


@pytest.mark.parametrize(
    ("body", "detail"),
    [
        (
            {"error": {"message": "Unknown parameter: 'verbosity'.", "type": "invalid_request"}},
            "status 400: Unknown parameter: 'verbosity'.",
        ),
        ({"message": "temperature must be 1"}, "status 400: temperature must be 1"),
        ({"error": "odd"}, "status 400."),
        ("not json", "status 400."),
    ],
)
async def test_a_rejection_carries_the_providers_reason(body: object, detail: str) -> None:
    response = httpx2.Response(400, json=body) if isinstance(body, dict) else httpx2.Response(400)

    with pytest.raises(ServiceError) as raised:
        await make_client(Recorder(response)).complete(MESSAGES)

    assert str(raised.value) == f"The LLM endpoint refused the request with {detail}"


async def test_a_long_reason_is_cut_short() -> None:
    response = httpx2.Response(400, json={"error": {"message": "x" * 2000}})

    with pytest.raises(ServiceError) as raised:
        await make_client(Recorder(response)).complete(MESSAGES)

    assert len(str(raised.value)) < 600


async def test_stream_errors_become_domain_errors() -> None:
    client = make_client(Recorder(httpx2.Response(503, json={"error": {"message": "loading"}})))

    with pytest.raises(ServiceUnavailableError):
        await collect(client)


async def test_an_error_partway_through_a_stream_becomes_a_domain_error() -> None:
    recorder = Recorder(streamed(chunk("Hel"), {"error": {"message": "the server stopped"}}))
    parts: list[StreamPart] = []

    async def read() -> None:
        async for part in make_client(recorder).stream(MESSAGES):
            parts.append(part)

    with pytest.raises(ServiceError):
        await read()

    assert parts == [ContentDelta(text="Hel")]  # what came before the error, and no end


@pytest.mark.parametrize(
    ("network_error", "error"),
    [
        (httpx2.ConnectError("refused"), ServiceUnavailableError),
        (httpx2.ReadTimeout("slow"), ServiceTimeoutError),
    ],
)
async def test_network_failures_become_domain_errors(
    network_error: httpx2.TransportError, error: type[ServiceError]
) -> None:
    def handler(_request: httpx2.Request) -> httpx2.Response:
        raise network_error

    with pytest.raises(error):
        await make_client(handler).complete(MESSAGES)


@pytest.mark.parametrize(
    ("status", "ready"),
    [
        (200, True),
        (400, True),  # it answered; it refused only the probe's max_tokens
        (401, False),  # a wrong key
        (404, False),  # no such model
        (503, False),  # loading
    ],
)
async def test_is_ready_tries_a_minimal_completion(status: int, ready: bool) -> None:
    """A real completion, not `/v1/models`: see the docstring on `is_ready` for why."""
    recorder = Recorder(httpx2.Response(status, json=completion_body("pong")))

    assert await make_client(recorder).is_ready() is ready

    assert recorder.requests[-1].url.path == "/v1/chat/completions"
    assert recorder.payload["max_tokens"] == 1
    assert recorder.requests[-1].extensions["timeout"]["read"] == READINESS_TIMEOUT_SECONDS


async def test_aclose_closes_the_http_connection_pool() -> None:
    http = httpx2.AsyncClient(transport=httpx2.MockTransport(Recorder(httpx2.Response(200))))

    await make_client(Recorder(httpx2.Response(200)), http).aclose()

    assert http.is_closed


def test_unexpected_sdk_errors_become_generic_llm_errors() -> None:
    odd = openai.APIError("odd", httpx2.Request("GET", "http://llm.test/v1"), body=None)

    assert type(translate(odd, SERVICE)) is ServiceError


class Replies:
    """A mock-transport handler that answers each request with the next step, a response or a
    network failure to raise, the last one repeated; and keeps every request."""

    def __init__(self, *steps: httpx2.Response | httpx2.TransportError) -> None:
        self.steps = steps
        self.requests: list[httpx2.Request] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        step = self.steps[min(len(self.requests), len(self.steps)) - 1]
        if isinstance(step, httpx2.TransportError):
            raise step
        return step


@pytest.mark.parametrize(
    "failure",
    [
        httpx2.Response(503),  # loading, or overloaded
        httpx2.Response(500),
        httpx2.Response(429),  # rate-limited
        httpx2.ConnectError("refused"),  # restarting: the request never reached the model
    ],
)
async def test_a_failure_that_can_pass_is_retried(
    failure: httpx2.Response | httpx2.TransportError,
) -> None:
    replies = Replies(failure, httpx2.Response(200, json=completion_body("Hi!")))

    completion = await make_client(replies, retries=2).complete(MESSAGES)

    assert completion.content == "Hi!"
    assert len(replies.requests) == 2


async def test_a_timeout_is_never_retried() -> None:
    replies = Replies(httpx2.ReadTimeout("slow"), httpx2.Response(200, json=completion_body("Hi!")))

    with pytest.raises(ServiceTimeoutError):
        await make_client(replies, retries=2).complete(MESSAGES)

    # One request: a second would start the same generation again, and wait as long.
    assert len(replies.requests) == 1


async def test_a_rejected_request_is_never_retried() -> None:
    replies = Replies(httpx2.Response(400), httpx2.Response(200, json=completion_body("Hi!")))

    with pytest.raises(ServiceError):
        await make_client(replies, retries=2).complete(MESSAGES)

    assert len(replies.requests) == 1


async def test_retries_stop_at_the_limit_each_waiting_twice_as_long(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    waits: list[float] = []

    async def sleep(seconds: float) -> None:
        waits.append(seconds)

    monkeypatch.setattr("app.llm.openai_compatible_client.asyncio.sleep", sleep)
    replies = Replies(httpx2.Response(503))

    with pytest.raises(ServiceUnavailableError):
        await make_client(replies, retries=2, retry_delay_seconds=0.5).complete(MESSAGES)

    assert len(replies.requests) == 3
    assert waits == [0.5, 1.0]
    assert "retrying in 0.5 s (retry 1 of 2)" in caplog.text


async def test_a_stream_is_retried_until_it_opens() -> None:
    replies = Replies(httpx2.Response(503), streamed(chunk("Hel"), chunk("lo"), "[DONE]"))

    parts = await collect(make_client(replies, retries=2))

    assert parts[:2] == [ContentDelta(text="Hel"), ContentDelta(text="lo")]
    assert len(replies.requests) == 2


@pytest.mark.parametrize("failure", [httpx2.Response(503), httpx2.ReadTimeout("slow")])
async def test_readiness_is_tried_once(failure: httpx2.Response | httpx2.TransportError) -> None:
    replies = Replies(failure, httpx2.Response(200, json=completion_body("pong")))

    assert await make_client(replies, retries=2).is_ready() is False

    # Within its timeout: never three attempts of five seconds each.
    assert len(replies.requests) == 1


def models_body(*models: dict[str, object]) -> httpx2.Response:
    entries = [{"object": "model", "created": 0, "owned_by": "test", **m} for m in models]
    return httpx2.Response(200, json={"object": "list", "data": entries})


async def test_model_info_reads_the_inputs_the_server_reports_for_the_model() -> None:
    recorder = Recorder(
        models_body(
            {"id": "other"},
            # The order is the server's; unknown inputs, such as files, are left out.
            {"id": "test-model", "architecture": {"input_modalities": ["video", "file", "text"]}},
        )
    )

    info = await make_client(recorder).model_info()

    assert info == ModelInfo(model="test-model", inputs=["text", "video"])
    assert str(recorder.requests[0].url) == "http://llm.test/v1/models"


async def test_model_info_takes_the_only_model_listed_whatever_its_name() -> None:
    # llama.cpp lists the model it loaded under its own name, not the configured one.
    recorder = Recorder(
        models_body({"id": "unsloth/Qwen3.5-4B-GGUF", "input_modalities": ["image", "text"]})
    )

    info = await make_client(recorder).model_info()

    assert info == ModelInfo(model="unsloth/Qwen3.5-4B-GGUF", inputs=["text", "image"])


@pytest.mark.parametrize(
    "response",
    [
        models_body({"id": "test-model"}),  # listed, with nothing said of its inputs
        models_body({"id": "a"}, {"id": "b"}),  # several listed, none under its name
        models_body(),
    ],
)
async def test_a_model_whose_inputs_are_not_reported_takes_text(response: httpx2.Response) -> None:
    info = await make_client(Recorder(response)).model_info()

    assert info == ModelInfo(model="test-model", inputs=["text"])


async def test_configured_inputs_are_trusted_without_asking_the_server() -> None:
    recorder = Recorder(models_body())
    sdk = AsyncOpenAI(
        base_url="http://llm.test/v1",
        api_key="test",
        max_retries=0,
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(recorder)),
    )

    info = await OpenAICompatibleClient(sdk, model="m", inputs=["image"]).model_info()

    assert info == ModelInfo(model="m", inputs=["text", "image"])
    assert recorder.requests == []


async def test_model_info_failures_become_domain_errors() -> None:
    client = make_client(Recorder(httpx2.Response(503)))

    with pytest.raises(ServiceUnavailableError, match="503"):
        await client.model_info()
