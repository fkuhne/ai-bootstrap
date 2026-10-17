"""The /api/rag endpoints: an app stores its chunks, lists what's stored and deletes a
document's chunks; a question searches them, and is answered from them, citing them
(docs/foundations.md#rag)."""

from collections.abc import AsyncIterable

from fastapi import APIRouter, status
from fastapi.sse import EventSourceResponse, ServerSentEvent

from app.core.errors import AppError, described, error_event
from app.llm.http import LLM_ERROR_RESPONSES
from app.llm.llm_client import ContentDelta, ReasoningDelta, StreamEnd
from app.modules.rag.answers import REFUSAL
from app.modules.rag.dependencies import AnswererDep, ChunkIndexDep, GroundingDep
from app.modules.rag.schemas import (
    Deleted,
    RagAnswer,
    RagDoneEvent,
    RagQuestion,
    RagSourcesEvent,
    SearchRequest,
    SearchResult,
    SourceList,
    Stored,
    StoreRequest,
)

router = APIRouter(prefix="/rag", tags=["rag"])

RAG_ERROR_RESPONSES = described(
    {
        status.HTTP_409_CONFLICT: "The collection holds another embedding model's vectors",
        status.HTTP_429_TOO_MANY_REQUESTS: "The embeddings' provider is rate-limiting",
        status.HTTP_502_BAD_GATEWAY: (
            "The embedding model or the store refused, such as a text too long"
        ),
        status.HTTP_503_SERVICE_UNAVAILABLE: "The embedding model or the store can't be reached",
        status.HTTP_504_GATEWAY_TIMEOUT: "The embedding model or the store didn't answer in time",
    }
)


@router.put(
    "/chunks",
    summary="Store chunks",
    description="Embeds each chunk, and keeps it with its BM25 weights, replacing any chunk "
    "stored before under its id. The first store makes the collection for the embedding "
    "model; a later one with another model is refused with 409.",
    responses=RAG_ERROR_RESPONSES,
)
async def store_chunks(body: StoreRequest, index: ChunkIndexDep) -> Stored:
    return Stored(stored=await index.store(body.chunks))


@router.get(
    "/sources",
    summary="The sources stored",
    description="Each source the stored chunks came from, by name, and how many chunks it has.",
    responses=RAG_ERROR_RESPONSES,
)
async def list_sources(index: ChunkIndexDep) -> SourceList:
    return SourceList(sources=await index.sources())


@router.delete(
    "/sources/{source:path}",
    summary="Delete a source's chunks",
    description="Removes every chunk of the source, as before storing a document's new version, "
    "and says how many. A source may hold slashes, such as `help/returns.md`.",
    responses=RAG_ERROR_RESPONSES,
)
async def delete_source(source: str, index: ChunkIndexDep) -> Deleted:
    return Deleted(deleted=await index.delete_source(source))


@router.post(
    "/search",
    summary="Search the chunks",
    description="The chunks that best match the query, best first: by meaning and words fused "
    "by rank (`hybrid`), by meaning alone (`dense`), or by words alone (`words`). Each hit has "
    "its score in that mode, and its similarity to the query whatever the mode.",
    responses=RAG_ERROR_RESPONSES,
)
async def search(body: SearchRequest, index: ChunkIndexDep) -> SearchResult:
    hits = await index.search(body.query, limit=body.limit, mode=body.mode, sources=body.sources)
    return SearchResult(hits=hits)


@router.post(
    "/ask",
    summary="Answer from the chunks, whole",
    description="Searches the chunks for the last message, the question, and asks the model "
    "with the best of them, numbered, before the conversation; the model cites them as [1]. "
    "When no chunk is found, or none as similar as RAG_MIN_SIMILARITY asks, the answer is "
    f"{REFUSAL!r} and the model isn't asked.",
    responses={**RAG_ERROR_RESPONSES, **LLM_ERROR_RESPONSES},
)
async def ask(body: RagQuestion, answerer: AnswererDep) -> RagAnswer:
    return await answerer.answer(body)


# The event each part of the model's answer is sent as.
EVENTS: dict[type, str] = {ReasoningDelta: "reasoning", ContentDelta: "token"}


@router.post(
    "/ask/stream",
    response_class=EventSourceResponse,
    summary="Answer from the chunks, streamed as server-sent events",
    description="As /api/rag/ask: first a `sources` event, the chunks the model is given; then "
    "`reasoning` and `token` events; then `done`. A refused question gets its answer as one "
    "`token`. A failure once the stream has started ends it with an `error` event.",
    responses={**RAG_ERROR_RESPONSES, **LLM_ERROR_RESPONSES},
)
async def ask_stream(
    grounding: GroundingDep, answerer: AnswererDep
) -> AsyncIterable[ServerSentEvent]:
    yield ServerSentEvent(event="sources", data=RagSourcesEvent(sources=grounding.sources))
    if grounding.refused:
        yield ServerSentEvent(event="token", data=ContentDelta(text=REFUSAL))
        yield ServerSentEvent(event="done", data=RagDoneEvent(refused=True))
        return
    try:
        async for part in answerer.stream(grounding):
            if isinstance(part, StreamEnd):
                done = RagDoneEvent(**part.model_dump(), refused=False)
                yield ServerSentEvent(event="done", data=done)
            else:
                yield ServerSentEvent(event=EVENTS[type(part)], data=part)
    except AppError as error:
        yield error_event(error)
