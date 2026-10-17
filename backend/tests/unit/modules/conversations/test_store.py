"""The conversation store on the in-memory database."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import func, select

from app.core.errors import ServiceUnavailableError
from app.llm.llm_client import ImagePart, ImageURL, TextPart, text_of
from app.modules.conversations.conversation_store import StoredContent, StoredTurn, title_from
from app.modules.conversations.database.config import DatabaseSettings
from app.modules.conversations.database.database import Database
from app.modules.conversations.exceptions import ConversationNotFoundError
from app.modules.conversations.models import TITLE_MAX_CHARS, Message, Role
from app.modules.conversations.sql_conversation_store import SqlConversationStore
from tests.unit.modules.conversations.helpers import DETAILS, UNREACHABLE_DATABASE_URL

pytestmark = pytest.mark.anyio

IMAGE = ImagePart(image_url=ImageURL(url="data:image/png;base64,AAAA"))


@pytest.fixture
def store(database: Database) -> SqlConversationStore:
    return SqlConversationStore(database.sessions)


async def turn(
    store: SqlConversationStore,
    user: UUID,
    conversation: UUID,
    question: StoredContent,
    *,
    asked_at: datetime | None = None,
) -> StoredTurn:
    return await store.add_turn(
        user,
        conversation,
        question=question,
        asked_at=asked_at or datetime.now(UTC),
        answer=f"The answer to: {text_of(question)}",
        reasoning="Thinking it over.",
        details=DETAILS,
    )


async def test_a_new_conversation_is_listed_without_a_title(store: SqlConversationStore) -> None:
    user = uuid4()

    created = await store.create_conversation(user)

    assert created.title is None
    assert created.updated_at == created.created_at  # never updated yet
    assert created.created_at.tzinfo == UTC
    assert await store.list_conversations(user) == [created]
    assert (await store.get_conversation(user, created.id)).messages == []


async def test_each_user_sees_only_their_conversations_newest_first(
    store: SqlConversationStore,
) -> None:
    user, someone_else = uuid4(), uuid4()
    older = await store.create_conversation(user)
    newer = await store.create_conversation(user)
    await store.create_conversation(someone_else)

    await turn(store, user, older.id, "What is an LLM?")

    listed = await store.list_conversations(user)
    assert [c.id for c in listed] == [older.id, newer.id]  # the turn made it the latest
    assert listed[0].updated_at > older.updated_at
    assert len(await store.list_conversations(someone_else)) == 1


async def test_the_first_question_names_the_conversation(store: SqlConversationStore) -> None:
    user = uuid4()
    conversation = await store.create_conversation(user)

    await turn(store, user, conversation.id, "What is\nan  LLM?")
    await turn(store, user, conversation.id, "And a token?")

    stored = await store.get_conversation(user, conversation.id)
    assert stored.title == "What is an LLM?"


async def test_a_question_without_text_leaves_the_title_to_the_next(
    store: SqlConversationStore,
) -> None:
    user = uuid4()
    conversation = await store.create_conversation(user)

    await turn(store, user, conversation.id, [IMAGE])
    assert (await store.get_conversation(user, conversation.id)).title is None

    await turn(store, user, conversation.id, [TextPart(text="What color is it?"), IMAGE])
    assert (await store.get_conversation(user, conversation.id)).title == "What color is it?"


async def test_each_message_follows_the_one_before(store: SqlConversationStore) -> None:
    user = uuid4()
    conversation = await store.create_conversation(user)

    first = await turn(store, user, conversation.id, "What is an LLM?")
    second = await turn(store, user, conversation.id, [TextPart(text="And this?"), IMAGE])

    messages = (await store.get_conversation(user, conversation.id)).messages
    assert messages == [first.question, first.answer, second.question, second.answer]
    assert [m.role for m in messages] == [Role.USER, Role.ASSISTANT] * 2
    assert [m.parent_id for m in messages] == [None, *[m.id for m in messages[:-1]]]
    # The content comes back as it was given, parts included; an answer has its reasoning and
    # details, a question none.
    assert messages[2].content == [TextPart(text="And this?"), IMAGE]
    assert (messages[1].reasoning, messages[1].details) == ("Thinking it over.", DETAILS)
    assert (messages[0].reasoning, messages[0].details) == (None, None)


async def test_the_history_follows_the_parents_not_the_clock(store: SqlConversationStore) -> None:
    user = uuid4()
    conversation = await store.create_conversation(user)
    await turn(store, user, conversation.id, "What is an LLM?")

    # A question timed before the first one, as a clock set back could make it.
    await turn(store, user, conversation.id, "And off?", asked_at=datetime(2020, 1, 1, tzinfo=UTC))

    messages = (await store.get_conversation(user, conversation.id)).messages
    assert [m.content for m in messages[::2]] == ["What is an LLM?", "And off?"]


async def test_another_users_conversation_is_not_found(store: SqlConversationStore) -> None:
    owner, intruder = uuid4(), uuid4()
    conversation = await store.create_conversation(owner)

    with pytest.raises(ConversationNotFoundError):
        await store.get_conversation(intruder, conversation.id)
    with pytest.raises(ConversationNotFoundError):
        await store.delete_conversation(intruder, conversation.id)
    with pytest.raises(ConversationNotFoundError):
        await turn(store, intruder, conversation.id, "Whose is this?")

    untouched = await store.get_conversation(owner, conversation.id)
    assert (untouched.title, untouched.messages) == (None, [])


async def test_a_missing_conversation_is_not_found(store: SqlConversationStore) -> None:
    with pytest.raises(ConversationNotFoundError, match="No conversation"):
        await store.get_conversation(uuid4(), uuid4())


async def test_deleting_a_conversation_deletes_its_messages(
    store: SqlConversationStore, database: Database
) -> None:
    user = uuid4()
    conversation = await store.create_conversation(user)
    await turn(store, user, conversation.id, "What is an LLM?")

    await store.delete_conversation(user, conversation.id)

    assert await store.list_conversations(user) == []
    async with database.sessions() as session:
        left = select(func.count()).where(Message.conversation_id == conversation.id)
        assert await session.scalar(left) == 0


async def test_an_unusable_database_raises_a_store_error() -> None:
    database = Database.connect(DatabaseSettings(url=SecretStr(UNREACHABLE_DATABASE_URL)))
    store = SqlConversationStore(database.sessions)

    with pytest.raises(ServiceUnavailableError, match="unavailable"):
        await store.list_conversations(uuid4())
    await database.aclose()


@pytest.mark.parametrize(
    ("question", "title"),
    [
        ("What is an LLM?", "What is an LLM?"),
        ("  What is\nan\tLLM?  ", "What is an LLM?"),
        ("x" * TITLE_MAX_CHARS, "x" * TITLE_MAX_CHARS),
        ("x" * (TITLE_MAX_CHARS + 1), "x" * (TITLE_MAX_CHARS - 1) + "…"),
        ("word " * 20, ("word " * 12)[: TITLE_MAX_CHARS - 1].rstrip() + "…"),
        ([TextPart(text="Describe"), IMAGE, TextPart(text="this.")], "Describe this."),
        ([IMAGE], None),
        ("   ", None),
    ],
)
def test_a_title_is_the_questions_text_on_one_line_cut_to_its_limit(
    question: StoredContent, title: str | None
) -> None:
    assert title_from(question) == title
    assert len(title_from(question) or "") <= TITLE_MAX_CHARS
