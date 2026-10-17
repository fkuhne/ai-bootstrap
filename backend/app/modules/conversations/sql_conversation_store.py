"""The conversation store on the database, through SQLAlchemy."""

from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager
from datetime import datetime
from uuid import UUID, uuid4

from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import ServiceUnavailableError
from app.modules.conversations.conversation_store import (
    AnswerDetails,
    ConversationStore,
    ConversationSummary,
    ConversationWithMessages,
    StoredContent,
    StoredMessage,
    StoredTurn,
    title_from,
)
from app.modules.conversations.database.base import utc_now
from app.modules.conversations.exceptions import ConversationNotFoundError
from app.modules.conversations.models import Conversation, Message, Role

CONTENT = TypeAdapter[StoredContent](StoredContent)


class SqlConversationStore(ConversationStore):
    """Conversations and their messages in the database.

    Each method runs in one short transaction of its own, so a connection is held for
    milliseconds, never while the model answers.
    """

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def create_conversation(self, user_id: UUID) -> ConversationSummary:
        now = utc_now()
        conversation = Conversation(id=uuid4(), user_id=user_id, created_at=now, updated_at=now)
        async with self._transaction() as session:
            session.add(conversation)
        return _summary(conversation)

    async def list_conversations(self, user_id: UUID) -> list[ConversationSummary]:
        async with self._transaction() as session:
            conversations = await session.scalars(
                select(Conversation)
                .where(Conversation.user_id == user_id)
                .order_by(Conversation.updated_at.desc(), Conversation.created_at.desc())
            )
            return [_summary(conversation) for conversation in conversations]

    async def get_conversation(
        self, user_id: UUID, conversation_id: UUID
    ) -> ConversationWithMessages:
        async with self._transaction() as session:
            conversation = await _owned(session, user_id, conversation_id)
            messages = _path(await _messages(session, conversation_id))
            return ConversationWithMessages(
                **_summary(conversation).model_dump(),
                messages=[_record(message) for message in messages],
            )

    async def delete_conversation(self, user_id: UUID, conversation_id: UUID) -> None:
        async with self._transaction() as session:
            # The database deletes its messages with it (ON DELETE CASCADE).
            await session.delete(await _owned(session, user_id, conversation_id))

    async def add_turn(
        self,
        user_id: UUID,
        conversation_id: UUID,
        *,
        question: StoredContent,
        asked_at: datetime,
        answer: str,
        reasoning: str | None,
        details: AnswerDetails,
    ) -> StoredTurn:
        answered_at = utc_now()
        async with self._transaction() as session:
            # Locked until the commit: a second turn on the same conversation, from another tab,
            # waits here, then follows this one instead of branching from the same message.
            conversation = await _owned(session, user_id, conversation_id, lock=True)
            path = _path(await _messages(session, conversation_id))
            asked = Message(
                id=uuid4(),
                conversation_id=conversation_id,
                parent_id=path[-1].id if path else None,
                role=Role.USER,
                content=CONTENT.dump_python(question, mode="json", exclude_none=True),
                created_at=asked_at,
            )
            answered = Message(
                id=uuid4(),
                conversation_id=conversation_id,
                parent_id=asked.id,
                role=Role.ASSISTANT,
                content=answer,
                reasoning=reasoning,
                created_at=answered_at,
                details=details.model_dump(mode="json"),
            )
            session.add_all([asked, answered])  # in this order: the answer points to the question
            conversation.updated_at = answered_at
            if conversation.title is None:
                conversation.title = title_from(question)
        return StoredTurn(question=_record(asked), answer=_record(answered))

    @asynccontextmanager
    async def _transaction(self) -> AsyncGenerator[AsyncSession]:
        """A session in a transaction, committed at the end, with database failures turned
        into the core's `ServiceUnavailableError`. `ConversationNotFoundError` passes through."""
        try:
            async with self._sessions.begin() as session:
                yield session
        # OSError: a refused connection or an unknown host, which SQLAlchemy doesn't wrap.
        except (SQLAlchemyError, OSError) as error:
            raise ServiceUnavailableError("The database is unavailable.") from error


async def _owned(
    session: AsyncSession, user_id: UUID, conversation_id: UUID, *, lock: bool = False
) -> Conversation:
    """The conversation, if it belongs to the user. `lock` holds its row until the commit
    (PostgreSQL's SELECT … FOR UPDATE; SQLite runs one write at a time anyway)."""
    query = select(Conversation).where(
        Conversation.id == conversation_id, Conversation.user_id == user_id
    )
    conversation = await session.scalar(query.with_for_update() if lock else query)
    if conversation is None:
        raise ConversationNotFoundError(conversation_id)
    return conversation


async def _messages(session: AsyncSession, conversation_id: UUID) -> Sequence[Message]:
    return (
        await session.scalars(select(Message).where(Message.conversation_id == conversation_id))
    ).all()


def _path(messages: Sequence[Message]) -> list[Message]:
    """The messages from the first question to the last message, following each one's parent.

    The last message is the one no other message follows. Nothing branches a conversation
    today, so there is one; were there several, the newest would be the end.
    """
    if not messages:
        return []
    by_id = {message.id: message for message in messages}
    followed = {message.parent_id for message in messages}
    node: Message | None = max(
        (message for message in messages if message.id not in followed),
        key=lambda message: message.created_at,
    )
    path = []
    while node is not None:
        path.append(node)
        node = by_id.get(node.parent_id) if node.parent_id is not None else None
    return path[::-1]


def _summary(conversation: Conversation) -> ConversationSummary:
    return ConversationSummary(
        id=conversation.id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


def _record(message: Message) -> StoredMessage:
    return StoredMessage(
        id=message.id,
        parent_id=message.parent_id,
        role=message.role,
        content=CONTENT.validate_python(message.content),
        reasoning=message.reasoning,
        created_at=message.created_at,
        details=None if message.details is None else AnswerDetails.model_validate(message.details),
    )
