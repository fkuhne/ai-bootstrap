"""The adapter talks to a mock transport: real HTTP parsing, no network."""

import json
from collections.abc import Callable

import httpx2
import pytest

from app.core.errors import (
    ServiceError,
    ServiceRateLimitedError,
    ServiceTimeoutError,
    ServiceUnavailableError,
)
from app.core.services import READINESS_TIMEOUT_SECONDS
from app.modules.decision.decision_model import DecisionRequest
from app.modules.decision.systemone_client import SystemOneClient
from tests.unit.modules.decision.helpers import ANSWER, REQUEST

pytestmark = pytest.mark.anyio

Handler = Callable[[httpx2.Request], httpx2.Response]


class Recorder:
    """A mock-transport handler that answers `response` and keeps every request."""

    def __init__(self, response: httpx2.Response) -> None:
        self.response = response
        self.requests: list[httpx2.Request] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        return self.response


def make_client(handler: Handler) -> SystemOneClient:
    http = httpx2.AsyncClient(
        base_url="http://decision.test/v1",
        headers={"Authorization": "Bearer k1"},
        transport=httpx2.MockTransport(handler),
    )
    return SystemOneClient(http, model="test-model")


def request() -> DecisionRequest:
    return DecisionRequest.model_validate(REQUEST)


async def test_decide_posts_the_request_with_the_model_and_reads_the_answers() -> None:
    recorder = Recorder(httpx2.Response(200, json=ANSWER))

    decision = await make_client(recorder).decide(request())

    sent = recorder.requests[0]
    assert str(sent.url) == "http://decision.test/v1/systemone"
    assert sent.headers["authorization"] == "Bearer k1"
    assert json.loads(sent.content) == {**REQUEST, "model": "test-model"}
    assert decision.model_dump(exclude_none=True) == ANSWER


async def test_a_request_s_own_model_wins() -> None:
    recorder = Recorder(httpx2.Response(200, json=ANSWER))

    await make_client(recorder).decide(DecisionRequest.model_validate({**REQUEST, "model": "x"}))

    assert json.loads(recorder.requests[0].content)["model"] == "x"


@pytest.mark.parametrize(
    ("response", "error", "message"),
    [
        (httpx2.Response(429), ServiceRateLimitedError, "rate-limiting"),
        (httpx2.Response(503), ServiceUnavailableError, "failed with status 503"),
        (
            # llama.cpp's answer to a text longer than its batch: a refusal, not an outage.
            httpx2.Response(500, json={"error": {"message": "input (794 tokens) is too large"}}),
            ServiceError,
            r"refused the request with status 500: input \(794 tokens\) is too large$",
        ),
        (httpx2.Response(529), ServiceUnavailableError, "failed with status 529"),
        (
            httpx2.Response(501, json={"error": {"message": "not a decision model"}}),
            ServiceError,
            "refused the request with status 501: not a decision model$",
        ),
        (
            httpx2.Response(422, json={"detail": "questions.q.type: invalid"}),
            ServiceError,
            "status 422: questions.q.type: invalid",
        ),
        (httpx2.Response(400, json={"error": "nope"}), ServiceError, "status 400: nope"),
        (httpx2.Response(401, text="Unauthorized"), ServiceError, "status 401."),
        (httpx2.Response(400, json=[1, 2]), ServiceError, "status 400."),
    ],
)
async def test_refusals_and_failures_become_the_module_s_errors(
    response: httpx2.Response, error: type[ServiceError], message: str
) -> None:
    with pytest.raises(error, match=message) as raised:
        await make_client(Recorder(response)).decide(request())

    assert type(raised.value) is error


async def test_a_long_reason_is_cut_short() -> None:
    response = httpx2.Response(400, json={"error": {"message": "x" * 600}})

    with pytest.raises(ServiceError) as raised:
        await make_client(Recorder(response)).decide(request())

    assert str(raised.value).endswith(": " + "x" * 500)


@pytest.mark.parametrize(
    ("failure", "error"),
    [
        (httpx2.ReadTimeout("slow"), ServiceTimeoutError),
        (httpx2.ConnectError("refused"), ServiceUnavailableError),
    ],
)
async def test_network_failures_become_the_module_s_errors(
    failure: httpx2.TransportError, error: type[ServiceError]
) -> None:
    def fail(_request: httpx2.Request) -> httpx2.Response:
        raise failure

    with pytest.raises(error):
        await make_client(fail).decide(request())


@pytest.mark.parametrize("body", [b"not json", b'{"model": "m"}'])
async def test_an_answer_in_an_unknown_shape_is_an_error(body: bytes) -> None:
    with pytest.raises(ServiceError, match="unknown shape"):
        await make_client(Recorder(httpx2.Response(200, content=body))).decide(request())


@pytest.mark.parametrize(
    ("response", "ready"),
    [(httpx2.Response(200, json=ANSWER), True), (httpx2.Response(501), False)],
)
async def test_readiness_asks_one_small_question_with_a_short_timeout(
    response: httpx2.Response, ready: bool
) -> None:
    recorder = Recorder(response)

    assert await make_client(recorder).is_ready() is ready

    sent = recorder.requests[0]
    assert json.loads(sent.content)["questions"]["ready"]["type"] == "noul"
    assert sent.extensions["timeout"]["read"] == READINESS_TIMEOUT_SECONDS


async def test_aclose_closes_the_http_connection_pool() -> None:
    http = httpx2.AsyncClient(transport=httpx2.MockTransport(Recorder(httpx2.Response(200))))

    await SystemOneClient(http, model="m").aclose()

    assert http.is_closed
