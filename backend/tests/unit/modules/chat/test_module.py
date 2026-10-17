"""The chat module as the app runs it: its switch, and its published example."""

import httpx2
import pytest

from app.core.config import forget_settings
from app.main import create_app
from app.modules.chat import MODULE
from app.modules.chat.schemas import ChatRequest
from app.openapi import schema

pytestmark = pytest.mark.anyio


def test_the_module_is_on_by_default_and_its_switch_turns_it_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert MODULE.enabled() is True

    monkeypatch.setenv("CHAT_ENABLED", "0")
    forget_settings()

    assert MODULE.enabled() is False


async def test_off_there_are_no_endpoints(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHAT_ENABLED", "0")
    app = create_app()
    transport = httpx2.ASGITransport(app=app)
    async with httpx2.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/chat", json={"messages": []})

    assert response.status_code == httpx2.codes.NOT_FOUND
    assert MODULE not in app.state.modules


def test_the_published_example_is_a_valid_request() -> None:
    # The example as the schema publishes it, which the docs page offers to send: the schema
    # drops null values, so an example must hold without them.
    for example in schema()["components"]["schemas"]["ChatRequest"]["examples"]:
        ChatRequest.model_validate(example)
