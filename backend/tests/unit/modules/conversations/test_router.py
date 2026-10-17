"""The /api/conversations endpoints, on the real store over in-memory SQLite."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import httpx2
import pytest
from fastapi import FastAPI
from pydantic import SecretStr
from starlette.requests import Request

from app.core.errors import ServiceUnavailableError
from app.llm.llm_client import ImagePart, ImageURL, TextPart
from app.modules.conversations.database.config import DatabaseSettings
from app.modules.conversations.database.database import Database
from app.modules.conversations.dependencies import get_conversation_store
from app.modules.conversations.sql_conversation_store import SqlConversationStore
from tests.helpers import USAGE, ScriptedLLM, UseLLM, events
from tests.unit.modules.conversations.helpers import DETAILS, UNREACHABLE_DATABASE_URL

pytestmark = pytest.mark.anyio

ALICE = str(uuid4())
BOB = str(uuid4())


@pytest.fixture
def store(app: FastAPI, database: Database) -> SqlConversationStore:
    """The store the endpoints use, as the lifespan sets it."""
    store = SqlConversationStore(database.sessions)
    app.dependency_overrides[get_conversation_store] = lambda: store
    return store


def as_user(user: str) -> dict[str, str]:
    return {"X-User-Id": user}


async def start(client: httpx2.AsyncClient, user: str) -> str:
    response = await client.post("/api/conversations", headers=as_user(user))
    assert response.status_code == httpx2.codes.CREATED
    return str(response.json()["id"])


@pytest.mark.usefixtures("store")
async def test_a_started_conversation_is_listed(client: httpx2.AsyncClient) -> None:
    started = await client.post("/api/conversations", headers=as_user(ALICE))

    listed = await client.get("/api/conversations", headers=as_user(ALICE))

    assert started.status_code == httpx2.codes.CREATED
    assert started.json()["title"] is None
    assert listed.json() == [started.json()]


@pytest.mark.usefixtures("store")
async def test_each_user_lists_only_their_conversations(client: httpx2.AsyncClient) -> None:
    alices = await start(client, ALICE)
    await start(client, BOB)

    listed = await client.get("/api/conversations", headers=as_user(ALICE))

    assert [c["id"] for c in listed.json()] == [alices]


async def test_an_opened_conversation_has_every_message(
    client: httpx2.AsyncClient, store: SqlConversationStore
) -> None:
    conversation = await start(client, ALICE)
    image = ImagePart(image_url=ImageURL(url="data:image/png;base64,AAAA"))
    await store.add_turn(
        UUID(ALICE),
        UUID(conversation),
        question=[TextPart(text="What color is this?"), image],
        asked_at=datetime.now(UTC),
        answer="Red.",
        reasoning="The square is red.",
        details=DETAILS,
    )

    opened = await client.get(f"/api/conversations/{conversation}", headers=as_user(ALICE))

    body = opened.json()
    assert opened.status_code == httpx2.codes.OK
    assert body["title"] == "What color is this?"
    question, answer = body["messages"]
    assert question["role"] == "user"
    assert question["content"] == [
        {"type": "text", "text": "What color is this?"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA", "detail": None}},
    ]
    assert (answer["role"], answer["content"], answer["reasoning"]) == (
        "assistant",
        "Red.",
        "The square is red.",
    )
    assert answer["details"]["model"] == DETAILS.model
    assert answer["details"]["usage"]["total_tokens"] == 20


@pytest.mark.usefixtures("store")
async def test_a_deleted_conversation_is_gone(client: httpx2.AsyncClient) -> None:
    conversation = await start(client, ALICE)

    deleted = await client.delete(f"/api/conversations/{conversation}", headers=as_user(ALICE))
    opened = await client.get(f"/api/conversations/{conversation}", headers=as_user(ALICE))

    assert deleted.status_code == httpx2.codes.NO_CONTENT
    assert deleted.content == b""
    assert opened.status_code == httpx2.codes.NOT_FOUND


@pytest.mark.usefixtures("store")
async def test_another_users_conversation_looks_missing(client: httpx2.AsyncClient) -> None:
    alices = await start(client, ALICE)

    opened = await client.get(f"/api/conversations/{alices}", headers=as_user(BOB))
    deleted = await client.delete(f"/api/conversations/{alices}", headers=as_user(BOB))
    missing = await client.get(f"/api/conversations/{uuid4()}", headers=as_user(BOB))

    assert opened.status_code == deleted.status_code == httpx2.codes.NOT_FOUND
    # The same answer as for an id that doesn't exist, but for the id itself.
    assert opened.json()["detail"] == f"No conversation {alices}."
    assert missing.status_code == httpx2.codes.NOT_FOUND
    still_there = await client.get(f"/api/conversations/{alices}", headers=as_user(ALICE))
    assert still_there.status_code == httpx2.codes.OK


@pytest.mark.usefixtures("store")
async def test_a_request_needs_the_user_id(client: httpx2.AsyncClient) -> None:
    response = await client.get("/api/conversations")

    assert response.status_code == httpx2.codes.UNPROCESSABLE_CONTENT


async def test_an_unusable_database_answers_503(
    app: FastAPI, client: httpx2.AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    database = Database.connect(DatabaseSettings(url=SecretStr(UNREACHABLE_DATABASE_URL)))
    app.dependency_overrides[get_conversation_store] = lambda: SqlConversationStore(
        database.sessions
    )

    response = await client.get("/api/conversations", headers=as_user(ALICE))
    await database.aclose()

    assert response.status_code == httpx2.codes.SERVICE_UNAVAILABLE
    assert response.json() == {"detail": "The database is unavailable."}


async def test_the_dependency_returns_the_store_the_lifespan_created(database: Database) -> None:
    app = FastAPI()
    app.state.conversation_store = SqlConversationStore(database.sessions)

    store = await get_conversation_store(Request({"type": "http", "app": app}))

    assert store is app.state.conversation_store


@pytest.mark.usefixtures("store")
async def test_asking_stores_the_question_and_the_answer(
    client: httpx2.AsyncClient, use_llm: UseLLM
) -> None:
    llm = ScriptedLLM()
    use_llm(llm)
    conversation = await start(client, ALICE)
    image = {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}}
    content = [{"type": "text", "text": "What is this?"}, image]

    asked = await client.post(
        f"/api/conversations/{conversation}/messages",
        json={"content": content, "parameters": {"temperature": 0.5}},
        headers=as_user(ALICE),
    )

    assert asked.status_code == httpx2.codes.CREATED
    turn = asked.json()
    assert (turn["answer"]["content"], turn["answer"]["reasoning"]) == ("Hello", "Greet.")
    assert turn["answer"]["details"]["model"] == "scripted"
    assert llm.sent[-1][1] == {"temperature": 0.5}
    opened = (await client.get(f"/api/conversations/{conversation}", headers=as_user(ALICE))).json()
    assert opened["title"] == "What is this?"
    assert opened["messages"] == [turn["question"], turn["answer"]]


@pytest.mark.parametrize("path", ["messages", "messages/stream"])
@pytest.mark.parametrize(
    "body",
    [
        {"content": ""},
        {"content": []},
        {"content": "Hi?", "parameters": {"stream": False}},
        {"question": "Hi?"},
    ],
)
@pytest.mark.usefixtures("store")
async def test_an_invalid_question_is_refused(
    client: httpx2.AsyncClient, use_llm: UseLLM, body: dict[str, Any], path: str
) -> None:
    llm = ScriptedLLM()
    use_llm(llm)
    conversation = await start(client, ALICE)

    asked = await client.post(
        f"/api/conversations/{conversation}/{path}", json=body, headers=as_user(ALICE)
    )

    assert asked.status_code == httpx2.codes.UNPROCESSABLE_CONTENT
    assert llm.sent == []


@pytest.mark.usefixtures("store")
async def test_a_model_failure_answers_its_status_and_stores_nothing(
    client: httpx2.AsyncClient, use_llm: UseLLM
) -> None:
    use_llm(ScriptedLLM(ServiceUnavailableError("The LLM endpoint can't be reached.")))
    conversation = await start(client, ALICE)

    asked = await client.post(
        f"/api/conversations/{conversation}/messages",
        json={"content": "Hi?"},
        headers=as_user(ALICE),
    )

    assert asked.status_code == httpx2.codes.SERVICE_UNAVAILABLE
    opened = (await client.get(f"/api/conversations/{conversation}", headers=as_user(ALICE))).json()
    assert opened["messages"] == []


@pytest.mark.parametrize("path", ["messages", "messages/stream"])
@pytest.mark.usefixtures("store")
async def test_asking_in_another_users_conversation_answers_404_before_the_model(
    client: httpx2.AsyncClient, use_llm: UseLLM, path: str
) -> None:
    llm = ScriptedLLM()
    use_llm(llm)
    alices = await start(client, ALICE)

    asked = await client.post(
        f"/api/conversations/{alices}/{path}", json={"content": "Hi?"}, headers=as_user(BOB)
    )

    # A 404, not a stream: the conversation is checked before the response starts.
    assert asked.status_code == httpx2.codes.NOT_FOUND
    assert asked.headers["content-type"] == "application/json"
    assert llm.sent == []


@pytest.mark.usefixtures("store")
async def test_a_streamed_answer_ends_with_the_stored_ids(
    client: httpx2.AsyncClient, use_llm: UseLLM
) -> None:
    use_llm(ScriptedLLM())
    conversation = await start(client, ALICE)

    streamed = await client.post(
        f"/api/conversations/{conversation}/messages/stream",
        json={"content": "Hi?"},
        headers=as_user(ALICE),
    )

    found = events(streamed.text)
    assert [name for name, _ in found] == ["reasoning", "token", "token", "done"]
    done = found[-1][1]
    assert (done["model"], done["finish_reason"], done["usage"]) == ("scripted", "stop", USAGE)
    opened = (await client.get(f"/api/conversations/{conversation}", headers=as_user(ALICE))).json()
    assert [m["id"] for m in opened["messages"]] == [done["question_id"], done["answer_id"]]
    assert opened["messages"][1]["content"] == "Hello"


@pytest.mark.usefixtures("store")
async def test_a_failure_ends_the_stream_with_an_error_and_stores_nothing(
    client: httpx2.AsyncClient, use_llm: UseLLM
) -> None:
    use_llm(
        ScriptedLLM(ServiceUnavailableError("The LLM endpoint can't be reached."), pieces_first=2)
    )
    conversation = await start(client, ALICE)

    streamed = await client.post(
        f"/api/conversations/{conversation}/messages/stream",
        json={"content": "Hi?"},
        headers=as_user(ALICE),
    )

    assert events(streamed.text)[-1] == (
        "error",
        {"status": 503, "detail": "The LLM endpoint can't be reached."},
    )
    opened = (await client.get(f"/api/conversations/{conversation}", headers=as_user(ALICE))).json()
    assert opened["messages"] == []
