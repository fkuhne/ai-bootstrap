"""Answering in a conversation, on the real store over in-memory SQLite and a scripted model."""

from uuid import UUID, uuid4

import pytest

from app.core.errors import ServiceUnavailableError
from app.llm.llm_client import (
    ChatMessage,
    ContentDelta,
    ContentPart,
    ImagePart,
    ImageURL,
    ReasoningDelta,
    TextPart,
    Usage,
)
from app.modules.conversations.conversation_answerer import (
    ConversationAnswerer,
    TurnStored,
    history,
)
from app.modules.conversations.conversation_store import ConversationWithMessages
from app.modules.conversations.database.database import Database
from app.modules.conversations.sql_conversation_store import SqlConversationStore
from tests.helpers import USAGE, ScriptedLLM
from tests.unit.modules.conversations.helpers import DETAILS

pytestmark = pytest.mark.anyio

IMAGE = ImagePart(image_url=ImageURL(url="data:image/png;base64,AAAA"))


@pytest.fixture
def store(database: Database) -> SqlConversationStore:
    return SqlConversationStore(database.sessions)


async def empty(store: SqlConversationStore, user: UUID) -> ConversationWithMessages:
    created = await store.create_conversation(user)
    return await store.get_conversation(user, created.id)


async def test_asking_stores_the_question_and_the_answer(store: SqlConversationStore) -> None:
    user = uuid4()
    conversation = await empty(store, user)

    turn = await ConversationAnswerer(store, ScriptedLLM()).ask(
        user, conversation, "Hi?", {"temperature": 0.5}
    )

    assert (turn.question.content, turn.answer.content, turn.answer.reasoning) == (
        "Hi?",
        "Hello",
        "Greet.",
    )
    assert turn.answer.details is not None
    assert (turn.answer.details.model, turn.answer.details.first_token_ms) == ("scripted", None)
    assert turn.answer.details.total_ms >= 0
    stored = await store.get_conversation(user, conversation.id)
    assert stored.messages == [turn.question, turn.answer]
    assert stored.title == "Hi?"


async def test_the_model_gets_the_history_the_question_and_the_parameters(
    store: SqlConversationStore,
) -> None:
    user, llm = uuid4(), ScriptedLLM()
    answerer = ConversationAnswerer(store, llm)
    conversation = await empty(store, user)
    await answerer.ask(user, conversation, "Hi?", {})
    conversation = await store.get_conversation(user, conversation.id)

    question: list[ContentPart] = [TextPart(text="And this?"), IMAGE]
    await answerer.ask(user, conversation, question, {"seed": 42})

    messages, parameters = llm.sent[-1]
    assert [(m.role, m.content) for m in messages] == [
        ("user", "Hi?"),
        ("assistant", "Hello"),  # the answer, without its reasoning
        ("user", question),
    ]
    assert parameters == {"seed": 42}


async def test_an_empty_answer_stays_out_of_the_history(store: SqlConversationStore) -> None:
    user = uuid4()
    conversation = await empty(store, user)
    await store.add_turn(
        user,
        conversation.id,
        question="Think hard.",
        asked_at=conversation.created_at,
        answer="",  # the model spent its budget reasoning
        reasoning="Hmm…",
        details=DETAILS,
    )
    conversation = await store.get_conversation(user, conversation.id)

    sent = history(conversation, "And now?")

    assert sent == [
        ChatMessage(role="user", content="Think hard."),
        ChatMessage(role="user", content="And now?"),
    ]


async def test_a_stream_yields_the_pieces_then_the_stored_turn(
    store: SqlConversationStore,
) -> None:
    user = uuid4()
    conversation = await empty(store, user)

    events = [
        event
        async for event in ConversationAnswerer(store, ScriptedLLM()).stream(
            user, conversation, "Hi?", {}
        )
    ]

    assert events[:3] == [
        ReasoningDelta(text="Greet."),
        ContentDelta(text="Hel"),
        ContentDelta(text="lo"),
    ]
    stored = events[-1]
    assert isinstance(stored, TurnStored)
    assert stored.end.usage == Usage(**USAGE)
    answer = stored.turn.answer
    assert (answer.content, answer.reasoning) == ("Hello", "Greet.")
    assert answer.details is not None
    assert answer.details.first_token_ms is not None
    assert (await store.get_conversation(user, conversation.id)).messages == [
        stored.turn.question,
        answer,
    ]


async def test_a_failed_stream_stores_nothing(store: SqlConversationStore) -> None:
    user = uuid4()
    conversation = await empty(store, user)
    llm = ScriptedLLM(ServiceUnavailableError("down"), pieces_first=2)

    with pytest.raises(ServiceUnavailableError):
        async for _ in ConversationAnswerer(store, llm).stream(user, conversation, "Hi?", {}):
            pass

    assert (await store.get_conversation(user, conversation.id)).messages == []


async def test_an_abandoned_stream_stores_nothing(store: SqlConversationStore) -> None:
    user = uuid4()
    conversation = await empty(store, user)

    stream = ConversationAnswerer(store, ScriptedLLM()).stream(user, conversation, "Hi?", {})
    await anext(stream)  # the client reads one piece, then goes away
    await stream.aclose()

    assert (await store.get_conversation(user, conversation.id)).messages == []
