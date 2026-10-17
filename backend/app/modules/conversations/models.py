"""The tables of conversations and their messages.

A change here needs a migration:
docker compose run --rm backend-checks alembic revision --autogenerate -m "<change>"
"""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.modules.conversations.database.base import Base, JsonDocument, UtcDateTime, utc_now

# A title is the first question's text, cut to this length.
TITLE_MAX_CHARS = 60


class Role(StrEnum):
    """Who wrote a message."""

    USER = "user"
    ASSISTANT = "assistant"


class Conversation(Base):
    """One user's conversation. The user is the id `app.users` gives each request."""

    __tablename__ = "conversations"
    __table_args__ = (
        # A user's conversations, the most recently updated first.
        Index("ix_conversations_user_id_updated_at", "user_id", "updated_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID]
    # Empty until a question with text.
    title: Mapped[str | None] = mapped_column(String(TITLE_MAX_CHARS))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)
    # When the last turn was stored.
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)


class Message(Base):
    """A question or an answer, as written. Each one points to the message before it."""

    __tablename__ = "messages"
    __table_args__ = (
        # A conversation's messages, in the order they were written.
        Index("ix_messages_conversation_id_created_at", "conversation_id", "created_at"),
        # The roles as text with a check, rather than a PostgreSQL enum type: the same on SQLite,
        # and a new role needs no ALTER TYPE.
        CheckConstraint(f"role IN ({', '.join(repr(role.value) for role in Role)})", name="role"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE")
    )
    # Empty for a conversation's first question.
    parent_id: Mapped[UUID | None] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"))
    # Stored as its value, `user` or `assistant`; the check constraint above keeps it to those.
    role: Mapped[Role] = mapped_column(
        Enum(
            Role,
            native_enum=False,
            create_constraint=False,
            length=16,
            values_callable=lambda roles: [role.value for role in roles],
        )
    )
    # The content as the API takes it: text, or a list of parts with images, audio or video.
    # Written once and read whole, so JSON (jsonb on PostgreSQL).
    content: Mapped[Any] = mapped_column(JsonDocument)
    # An answer's reasoning, when the model showed it; empty for questions.
    reasoning: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)
    # How an answer was made: the model, the finish reason, the usage and the timings; empty
    # for questions.
    details: Mapped[dict[str, Any] | None] = mapped_column(JsonDocument)
