"""The /api/chat endpoints: the conversation goes to the model, the answer comes back whole or
streamed."""

from collections.abc import AsyncIterable

from fastapi import APIRouter
from fastapi.sse import EventSourceResponse, ServerSentEvent

from app.core.errors import AppError, error_event
from app.llm.dependencies import LLMClientDep
from app.llm.http import LLM_ERROR_RESPONSES
from app.llm.llm_client import Completion, ContentDelta, ReasoningDelta, StreamEnd
from app.modules.chat.schemas import ChatRequest

router = APIRouter(prefix="/chat", tags=["chat"])

# The event each stream part is sent as.
EVENTS: dict[type, str] = {ReasoningDelta: "reasoning", ContentDelta: "token", StreamEnd: "done"}


@router.post(
    "",
    summary="Ask the model, and get its whole answer",
    description="Sends the messages and parameters to the configured model and returns its "
    "answer, with its reasoning when the model shows it.",
    responses=LLM_ERROR_RESPONSES,
)
async def chat(body: ChatRequest, llm: LLMClientDep) -> Completion:
    return await llm.complete(body.messages, parameters=body.parameters)


@router.post(
    "/stream",
    response_class=EventSourceResponse,
    summary="Ask the model, and stream its answer as server-sent events",
    description="Emits `reasoning` events while the model reasons, `token` events with pieces of "
    "the answer, then `done` with the finish reason and the usage. If the model fails once the "
    "stream has started, an `error` event ends it instead. Closing the stream stops the model.",
)
async def chat_stream(body: ChatRequest, llm: LLMClientDep) -> AsyncIterable[ServerSentEvent]:
    try:
        async for part in llm.stream(body.messages, parameters=body.parameters):
            yield ServerSentEvent(event=EVENTS[type(part)], data=part)
    except AppError as error:
        yield error_event(error)
