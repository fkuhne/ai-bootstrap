"""Answering in a stored conversation: its history goes to the model with the new question,
and the turn is stored once the answer is complete."""

import logging
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.llm.llm_client import (
    ChatMessage,
    Completion,
    Content,
    ContentDelta,
    LLMClient,
    Parameters,
    ReasoningDelta,
    StreamEnd,
)
from app.modules.conversations.conversation_store import (
    AnswerDetails,
    ConversationStore,
    ConversationWithMessages,
    StoredTurn,
)
from app.modules.conversations.database.base import utc_now

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TurnStored:
    """The last event of a streamed answer: how the stream ended, and the turn as stored."""

    end: StreamEnd
    turn: StoredTurn


# What a streamed answer in a conversation sends: the reasoning and the answer's pieces, then
# the stored turn.
ConversationEvent = ReasoningDelta | ContentDelta | TurnStored


class ConversationAnswerer:
    """Answers a question within a conversation, and stores both.

    The conversation comes already read, and checked to be the user's, so a request for
    someone else's fails before anything runs or streams. The question and its answer are
    stored together once the answer is complete, so a failed or abandoned answer leaves the
    conversation as it was.
    """

    def __init__(self, store: ConversationStore, llm: LLMClient) -> None:
        self._store = store
        self._llm = llm

    async def ask(
        self,
        user_id: UUID,
        conversation: ConversationWithMessages,
        content: Content,
        parameters: Parameters,
    ) -> StoredTurn:
        asked_at, started = utc_now(), time.perf_counter()
        completion = await self._llm.complete(history(conversation, content), parameters=parameters)
        return await self._store_turn(
            user_id,
            conversation,
            content,
            asked_at,
            answer=completion,
            details=_details(completion.model, completion, started, first_token_ms=None),
        )

    async def stream(
        self,
        user_id: UUID,
        conversation: ConversationWithMessages,
        content: Content,
        parameters: Parameters,
    ) -> AsyncGenerator[ConversationEvent]:
        """The model's pieces as they come, then the stored turn. If the stream stops early,
        because the model failed or the client went away, nothing is stored."""
        asked_at, started = utc_now(), time.perf_counter()
        answer: list[str] = []
        reasoning: list[str] = []
        first_token_ms: float | None = None
        async for part in self._llm.stream(history(conversation, content), parameters=parameters):
            match part:
                case ReasoningDelta(text=text):
                    reasoning.append(text)
                    yield part
                case ContentDelta(text=text):
                    if first_token_ms is None:
                        first_token_ms = (time.perf_counter() - started) * 1000
                    answer.append(text)
                    yield part
                case _:  # the StreamEnd, last
                    completion = Completion(
                        content="".join(answer),
                        reasoning="".join(reasoning) or None,
                        model=part.model,
                        finish_reason=part.finish_reason,
                        usage=part.usage,
                    )
                    turn = await self._store_turn(
                        user_id,
                        conversation,
                        content,
                        asked_at,
                        answer=completion,
                        details=_details(part.model, part, started, first_token_ms),
                    )
                    yield TurnStored(end=part, turn=turn)

    async def _store_turn(
        self,
        user_id: UUID,
        conversation: ConversationWithMessages,
        content: Content,
        asked_at: datetime,
        *,
        answer: Completion,
        details: AnswerDetails,
    ) -> StoredTurn:
        turn = await self._store.add_turn(
            user_id,
            conversation.id,
            question=content,
            asked_at=asked_at,
            answer=answer.content,
            reasoning=answer.reasoning,
            details=details,
        )
        logger.debug(
            "Stored a turn in conversation %s, after %d messages.",
            conversation.id,
            len(conversation.messages),
        )
        return turn


def history(conversation: ConversationWithMessages, content: Content) -> list[ChatMessage]:
    """The conversation's messages as written, then the new question. An answer left empty,
    when the model spent its budget reasoning, is skipped: the model takes no empty message.
    Reasoning stays out: models expect only the answers back."""
    earlier = [
        ChatMessage(role=message.role.value, content=message.content)
        for message in conversation.messages
        if message.content
    ]
    return [*earlier, ChatMessage(role="user", content=content)]


def _details(
    model: str, outcome: Completion | StreamEnd, started: float, first_token_ms: float | None
) -> AnswerDetails:
    return AnswerDetails(
        model=model,
        finish_reason=outcome.finish_reason,
        usage=outcome.usage,
        first_token_ms=first_token_ms,
        total_ms=(time.perf_counter() - started) * 1000,
    )
