"""The decision module as the app runs it: its settings, its endpoint, and its readiness."""

from collections.abc import AsyncIterator

import httpx2
import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from app.core.config import forget_settings
from app.core.errors import (
    ServiceError,
    ServiceRateLimitedError,
    ServiceTimeoutError,
    ServiceUnavailableError,
)
from app.llm.dependencies import get_llm_client
from app.llm.fake_llm_client import FakeLLMClient
from app.main import create_app
from app.modules.decision import MODULE
from app.modules.decision.config import DecisionSettings
from app.modules.decision.decision_model import Decision, DecisionRequest
from app.modules.decision.factory import create_decision_model
from app.modules.decision.fake_decision_model import FakeDecisionModel
from app.modules.decision.systemone_client import SystemOneClient
from tests.unit.modules.decision.helpers import ANSWER, REQUEST

pytestmark = pytest.mark.anyio


class FailingModel(FakeDecisionModel):
    def __init__(self, error: ServiceError) -> None:
        super().__init__()
        self.error = error

    async def decide(self, request: DecisionRequest) -> Decision:
        raise self.error


@pytest.fixture
def decision_app() -> FastAPI:
    app = create_app(modules=[MODULE])
    app.state.decision_model = FakeDecisionModel()
    app.dependency_overrides[get_llm_client] = FakeLLMClient
    return app


@pytest.fixture
async def client(decision_app: FastAPI) -> AsyncIterator[httpx2.AsyncClient]:
    transport = httpx2.ASGITransport(app=decision_app)
    async with httpx2.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


def test_the_module_is_on_by_default_and_its_switch_turns_it_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = DecisionSettings()
    assert (settings.provider, str(settings.base_url)) == ("systemone", "http://decision:8080/v1")
    assert MODULE.enabled() is True

    monkeypatch.setenv("DECISION_ENABLED", "0")
    forget_settings()

    assert MODULE.enabled() is False


def test_the_provider_picks_the_implementation_and_no_longer_turns_it_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DECISION_PROVIDER", "off")

    with pytest.raises(ValidationError, match="'systemone' or 'fake'"):
        DecisionSettings()


async def test_decide_answers_under_the_questions_names(client: httpx2.AsyncClient) -> None:
    response = await client.post("/api/decide", json=REQUEST)

    assert response.status_code == httpx2.codes.OK
    assert set(response.json()["answers"]) == {"route", "angry", "urgency"}


async def test_an_invalid_request_is_refused(client: httpx2.AsyncClient) -> None:
    response = await client.post("/api/decide", json={"state": "x", "questions": {}})

    assert response.status_code == httpx2.codes.UNPROCESSABLE_CONTENT


@pytest.mark.parametrize(
    ("error", "status_code"),
    [
        (ServiceTimeoutError("slow"), httpx2.codes.GATEWAY_TIMEOUT),
        (ServiceUnavailableError("down"), httpx2.codes.SERVICE_UNAVAILABLE),
        (ServiceRateLimitedError("busy"), httpx2.codes.TOO_MANY_REQUESTS),
        (ServiceError("refused"), httpx2.codes.BAD_GATEWAY),
    ],
)
async def test_errors_become_http_errors(
    decision_app: FastAPI,
    client: httpx2.AsyncClient,
    error: ServiceError,
    status_code: int,
) -> None:
    decision_app.state.decision_model = FailingModel(error)

    response = await client.post("/api/decide", json=REQUEST)

    assert response.status_code == status_code
    assert response.json() == {"detail": str(error)}


@pytest.mark.parametrize(("ready", "status"), [(True, "ok"), (False, "unavailable")])
async def test_readiness_reports_the_decision_model(
    decision_app: FastAPI, client: httpx2.AsyncClient, ready: bool, status: str
) -> None:
    decision_app.state.decision_model = FakeDecisionModel(ready=ready)

    response = await client.get("/api/health/ready")

    assert response.json()["checks"]["decision"] == status


async def test_off_there_is_no_endpoint_and_no_readiness_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DECISION_ENABLED", "0")
    app = create_app()
    transport = httpx2.ASGITransport(app=app)
    async with httpx2.AsyncClient(transport=transport, base_url="http://test") as client:
        decide = await client.post("/api/decide", json=REQUEST)

    assert decide.status_code == httpx2.codes.NOT_FOUND
    # Readiness checks the app's modules, and this one isn't among them.
    assert MODULE not in app.state.modules


async def test_the_lifespan_creates_the_model_and_closes_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    monkeypatch.setenv("DECISION_PROVIDER", "fake")
    app = create_app()

    async with app.router.lifespan_context(app):
        model = app.state.decision_model
        assert isinstance(model, FakeDecisionModel)
        assert not model.closed

    assert model.closed


async def test_the_factory_builds_a_system_one_client_from_the_settings() -> None:
    sent: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        sent.append(request)
        return httpx2.Response(200, json=ANSWER)

    settings = DecisionSettings(
        provider="systemone",
        base_url="https://openrouter.ai/api/v1",  # type: ignore[arg-type]
        api_key="k2",  # type: ignore[arg-type]
        model="typesafe/jev-1.13",
        timeout_seconds=12,
    )

    model = create_decision_model(settings, transport=httpx2.MockTransport(handler))
    await model.decide(DecisionRequest.model_validate(REQUEST))
    await model.aclose()

    assert isinstance(model, SystemOneClient)
    assert str(sent[0].url) == "https://openrouter.ai/api/v1/systemone"
    assert sent[0].headers["authorization"] == "Bearer k2"
    assert sent[0].extensions["timeout"]["read"] == 12
    assert isinstance(create_decision_model(DecisionSettings(provider="fake")), FakeDecisionModel)


async def test_the_example_in_the_api_s_docs_works(
    decision_app: FastAPI, client: httpx2.AsyncClient
) -> None:
    # The example as the published schema shows it, which the docs page offers to send.
    schema = decision_app.openapi()["components"]["schemas"]["DecisionRequest"]
    example = schema["examples"][0]

    response = await client.post("/api/decide", json=example)

    assert response.status_code == httpx2.codes.OK, response.json()
