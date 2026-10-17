"""The conversations module as the app runs it: its switch, its readiness, its database's life,
and what it publishes in the API's schema."""

import httpx2
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from app.core.config import forget_settings
from app.llm.dependencies import get_llm_client
from app.llm.fake_llm_client import FakeLLMClient
from app.main import create_app
from app.modules.conversations import MODULE
from app.modules.conversations.database.config import DatabaseSettings
from app.modules.conversations.database.database import Database
from app.modules.conversations.schemas import AskRequest
from app.modules.conversations.sql_conversation_store import SqlConversationStore
from app.openapi import schema
from tests.unit.modules.conversations.helpers import (
    MEMORY_DATABASE_URL,
    UNREACHABLE_DATABASE_URL,
)

pytestmark = pytest.mark.anyio


def client_for(app: FastAPI) -> httpx2.AsyncClient:
    return httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url="http://test")


def test_the_module_is_on_by_default_and_its_switch_turns_it_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert MODULE.enabled() is True

    monkeypatch.setenv("CONVERSATIONS_ENABLED", "0")
    forget_settings()

    assert MODULE.enabled() is False


async def test_off_there_are_no_endpoints(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONVERSATIONS_ENABLED", "0")
    app = create_app()

    async with client_for(app) as client:
        response = await client.get("/api/conversations")

    assert response.status_code == httpx2.codes.NOT_FOUND
    # Readiness checks the app's modules, and this one isn't among them.
    assert MODULE not in app.state.modules


@pytest.mark.parametrize(
    ("database_url", "status"),
    [(MEMORY_DATABASE_URL, "ok"), (UNREACHABLE_DATABASE_URL, "unavailable")],
)
async def test_readiness_reports_the_database(database_url: str, status: str) -> None:
    app = create_app(modules=[MODULE])
    app.dependency_overrides[get_llm_client] = FakeLLMClient
    app.state.database = Database.connect(DatabaseSettings(url=SecretStr(database_url)))

    async with client_for(app) as client:
        response = await client.get("/api/health/ready")
    await app.state.database.aclose()

    assert response.json()["checks"]["conversations"] == status


async def test_the_lifespan_connects_the_database_and_closes_it(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    monkeypatch.setenv("DATABASE_URL", MEMORY_DATABASE_URL)
    app = create_app(modules=[MODULE])
    closed: list[bool] = []

    async with app.router.lifespan_context(app):
        database = app.state.database
        assert await database.is_ready()
        assert isinstance(app.state.conversation_store, SqlConversationStore)
        close = database.aclose

        async def recording_close() -> None:
            closed.append(True)
            await close()

        monkeypatch.setattr(database, "aclose", recording_close)

    assert closed == [True]
    # The app's own logging, which replaces pytest's handlers, writes to stderr.
    logged = capsys.readouterr().err
    assert "Conversations in the database at sqlite+aiosqlite://." in logged


def test_its_streamed_event_is_in_the_api_s_schema() -> None:
    models = schema()["components"]["schemas"]

    assert {"question_id", "answer_id"} <= set(models["ConversationDoneEvent"]["properties"])


def test_the_published_example_is_a_valid_request() -> None:
    # The example as the schema publishes it, which the docs page offers to send: the schema
    # drops null values, so an example must hold without them.
    for example in schema()["components"]["schemas"]["AskRequest"]["examples"]:
        AskRequest.model_validate(example)
