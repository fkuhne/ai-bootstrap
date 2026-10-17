"""The conversation tables, on the in-memory database."""

from datetime import UTC
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from app.modules.conversations.database.database import Database
from app.modules.conversations.models import Conversation, Message, Role

pytestmark = pytest.mark.anyio

PARTS = [
    {"type": "text", "text": "What is this?"},
    {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}},
]
DETAILS = {"model": "test-model", "finish_reason": "stop", "total_ms": 480.5}


async def test_a_turn_is_stored_and_read_back(database: Database) -> None:
    conversation = Conversation(id=uuid4(), user_id=uuid4(), title="What is this?")
    question = Message(id=uuid4(), conversation_id=conversation.id, role=Role.USER, content=PARTS)
    answer = Message(
        id=uuid4(),
        conversation_id=conversation.id,
        parent_id=question.id,
        role=Role.ASSISTANT,
        content="A red square.",
        reasoning="The image is red.",
        details=DETAILS,
    )
    async with database.sessions.begin() as session:
        session.add_all([conversation, question, answer])

    async with database.sessions() as session:
        stored_question = await session.get_one(Message, question.id)
        stored_answer = await session.get_one(Message, answer.id)
        stored_conversation = await session.get_one(Conversation, conversation.id)

    assert (stored_question.role, stored_question.content) == (Role.USER, PARTS)
    assert (stored_question.parent_id, stored_question.details) == (None, None)
    assert (stored_answer.role, stored_answer.parent_id) == (Role.ASSISTANT, question.id)
    assert (stored_answer.content, stored_answer.reasoning) == (
        "A red square.",
        "The image is red.",
    )
    assert stored_answer.details == DETAILS
    # Filled in when written, and read back in UTC, although SQLite drops the zone.
    assert stored_conversation.created_at.tzinfo == UTC
    assert stored_answer.created_at.tzinfo == UTC


async def test_deleting_a_conversation_deletes_its_messages(database: Database) -> None:
    conversation = Conversation(id=uuid4(), user_id=uuid4())
    question = Message(id=uuid4(), conversation_id=conversation.id, role=Role.USER, content="Hi")
    answer = Message(
        conversation_id=conversation.id, parent_id=question.id, role=Role.ASSISTANT, content="Hello"
    )
    async with database.sessions.begin() as session:
        session.add_all([conversation, question, answer])

    async with database.sessions.begin() as session:
        await session.delete(await session.get_one(Conversation, conversation.id))

    async with database.sessions() as session:
        left = select(func.count()).where(Message.conversation_id == conversation.id)
        assert await session.scalar(left) == 0


async def test_a_message_needs_its_conversation(database: Database) -> None:
    with pytest.raises(IntegrityError):
        async with database.sessions.begin() as session:
            session.add(Message(conversation_id=uuid4(), role=Role.USER, content="Orphan"))


async def test_the_database_refuses_any_other_role(database: Database) -> None:
    async with database.sessions.begin() as session:
        conversation = Conversation(user_id=uuid4())
        session.add(conversation)

    with pytest.raises(IntegrityError, match="ck_messages_role"):
        async with database.sessions.begin() as session:
            await session.execute(
                text(
                    "INSERT INTO messages (id, conversation_id, role, content, created_at)"
                    " VALUES (:id, :conversation, 'system', '\"Hi\"', CURRENT_TIMESTAMP)"
                ),
                {"id": uuid4().hex, "conversation": conversation.id.hex},
            )
