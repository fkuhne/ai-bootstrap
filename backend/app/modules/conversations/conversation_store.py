"""What a conversation store keeps and returns, and its port."""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.llm.llm_client import ContentPart, Usage, text_of
from app.modules.conversations.models import TITLE_MAX_CHARS, Role

# A stored message's content: a question as the API took it, text or parts with images, audio
# or video; or an answer's text, which may be empty when the model spent its budget reasoning.
StoredContent = str | list[ContentPart]


class AnswerDetails(BaseModel):
    """How an answer was made, stored with it as JSON."""

    model_config = ConfigDict(frozen=True)

    model: str = Field(description="The model that wrote the answer.")
    finish_reason: str | None
    usage: Usage | None
    first_token_ms: float | None = Field(
        default=None, description="Until the first piece of the answer, when it was streamed."
    )
    total_ms: float


class StoredMessage(BaseModel):
    """A question or an answer, as it was written."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    parent_id: UUID | None = Field(description="The message before it; null for the first.")
    role: Role
    content: StoredContent
    reasoning: str | None = Field(
        default=None, description="An answer's reasoning, when the model showed it."
    )
    created_at: datetime
    details: AnswerDetails | None = Field(default=None, description="Null for questions.")


class ConversationSummary(BaseModel):
    """A conversation, without its messages."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    title: str | None = Field(description="The first question's text; null until there is one.")
    created_at: datetime
    updated_at: datetime = Field(description="When the last turn was stored.")


class ConversationWithMessages(ConversationSummary):
    """A conversation with all its messages, from the first question to the last answer."""

    messages: list[StoredMessage]


class StoredTurn(BaseModel):
    """A question and its answer, stored together."""

    model_config = ConfigDict(frozen=True)

    question: StoredMessage
    answer: StoredMessage


def title_from(question: StoredContent) -> str | None:
    """A conversation's title: the question's text on one line, cut to `TITLE_MAX_CHARS`;
    None when the question has no text, such as an image alone."""
    line = " ".join(text_of(question).split())
    if not line:
        return None
    if len(line) <= TITLE_MAX_CHARS:
        return line
    return line[: TITLE_MAX_CHARS - 1].rstrip() + "…"


class ConversationStore(Protocol):
    """Where each user's conversations are kept. Every method is scoped to one user: another
    user's conversation raises `ConversationNotFoundError`, as a missing one does. A database
    failure raises the core's `ServiceUnavailableError`."""

    async def create_conversation(self, user_id: UUID) -> ConversationSummary:
        """Start an empty conversation, without a title until its first question."""
        ...

    async def list_conversations(self, user_id: UUID) -> list[ConversationSummary]:
        """The user's conversations, the most recently updated first."""
        ...

    async def get_conversation(
        self, user_id: UUID, conversation_id: UUID
    ) -> ConversationWithMessages:
        """A conversation with its messages: the path from the last message back to the
        first, oldest first."""
        ...

    async def delete_conversation(self, user_id: UUID, conversation_id: UUID) -> None:
        """Delete a conversation and all its messages."""
        ...

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
        """Store a question and its answer together, after the conversation's last message.
        The first question with text also gives the conversation its title."""
        ...
