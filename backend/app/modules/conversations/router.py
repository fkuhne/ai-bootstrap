"""The /api/conversations endpoints: each user's conversations."""

from collections.abc import AsyncIterable
from uuid import UUID

from fastapi import APIRouter, status
from fastapi.sse import EventSourceResponse, ServerSentEvent

from app.core.errors import AppError, described, error_event
from app.llm.http import LLM_ERROR_RESPONSES
from app.llm.llm_client import ReasoningDelta
from app.modules.conversations.conversation_answerer import TurnStored
from app.modules.conversations.conversation_store import (
    ConversationSummary,
    ConversationWithMessages,
    StoredTurn,
)
from app.modules.conversations.dependencies import (
    ConversationAnswererDep,
    ConversationStoreDep,
    OwnedConversationDep,
)
from app.modules.conversations.schemas import AskRequest, ConversationDoneEvent
from app.users.dependencies import CurrentUserDep

router = APIRouter(prefix="/conversations", tags=["conversations"])

STORE_UNAVAILABLE = described({status.HTTP_503_SERVICE_UNAVAILABLE: "The database is unavailable"})
NOT_FOUND = (
    described(
        {
            status.HTTP_404_NOT_FOUND: "No such conversation for this user: it doesn't exist, was "
            "deleted, or belongs to another id",
        }
    )
    | STORE_UNAVAILABLE
)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Start a conversation",
    description="Starts an empty conversation. Its first question with text gives its title.",
    responses=STORE_UNAVAILABLE,
)
async def start_conversation(
    user_id: CurrentUserDep, store: ConversationStoreDep
) -> ConversationSummary:
    return await store.create_conversation(user_id)


@router.get(
    "",
    summary="List conversations",
    description="This user's conversations, without their messages, the most recently "
    "updated first.",
    responses=STORE_UNAVAILABLE,
)
async def list_conversations(
    user_id: CurrentUserDep, store: ConversationStoreDep
) -> list[ConversationSummary]:
    return await store.list_conversations(user_id)


@router.get(
    "/{conversation_id}",
    summary="Open a conversation",
    description="One conversation with all its messages, oldest first: every question as it "
    "was asked, and every answer with its reasoning and how it was made.",
    responses=NOT_FOUND,
)
async def open_conversation(
    conversation_id: UUID, user_id: CurrentUserDep, store: ConversationStoreDep
) -> ConversationWithMessages:
    return await store.get_conversation(user_id, conversation_id)


@router.delete(
    "/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a conversation",
    description="Deletes the conversation and all its messages. It can't be undone.",
    responses=NOT_FOUND,
)
async def delete_conversation(
    conversation_id: UUID, user_id: CurrentUserDep, store: ConversationStoreDep
) -> None:
    await store.delete_conversation(user_id, conversation_id)


@router.post(
    "/{conversation_id}/messages",
    status_code=status.HTTP_201_CREATED,
    summary="Ask in a conversation",
    description="Sends the conversation's messages and the new question to the model, with any "
    "parameters, and returns the question and the answer as stored: the answer with its "
    "reasoning and how it was made. If the model fails, nothing is stored.",
    responses={**NOT_FOUND, **LLM_ERROR_RESPONSES},
)
async def ask(
    body: AskRequest,
    user_id: CurrentUserDep,
    conversation: OwnedConversationDep,
    answerer: ConversationAnswererDep,
) -> StoredTurn:
    return await answerer.ask(user_id, conversation, body.content, body.parameters)


@router.post(
    "/{conversation_id}/messages/stream",
    response_class=EventSourceResponse,
    summary="Ask in a conversation, and stream the answer",
    description="The same answer as `/messages`, as server-sent events, like "
    "`/api/chat/stream`: `reasoning` and `token` events as the model writes, then `done` with "
    "how it ended and the ids the question and the answer were stored under. The turn is "
    "stored just before `done`. If the model or the database fails once the stream has "
    "started, an `error` event ends it, and nothing is stored; nor is anything if the client "
    "goes away first.",
    responses=NOT_FOUND,
)
async def ask_stream(
    body: AskRequest,
    user_id: CurrentUserDep,
    conversation: OwnedConversationDep,
    answerer: ConversationAnswererDep,
) -> AsyncIterable[ServerSentEvent]:
    try:
        async for event in answerer.stream(user_id, conversation, body.content, body.parameters):
            match event:
                case TurnStored():  # the last event
                    yield ServerSentEvent(event="done", data=_done(event))
                case ReasoningDelta():
                    yield ServerSentEvent(event="reasoning", data=event)
                case _:
                    yield ServerSentEvent(event="token", data=event)
    # The model's, the database's, or a conversation deleted while the model was answering.
    except AppError as error:
        yield error_event(error)


def _done(event: TurnStored) -> ConversationDoneEvent:
    return ConversationDoneEvent(
        model=event.end.model,
        finish_reason=event.end.finish_reason,
        usage=event.end.usage,
        question_id=event.turn.question.id,
        answer_id=event.turn.answer.id,
    )
