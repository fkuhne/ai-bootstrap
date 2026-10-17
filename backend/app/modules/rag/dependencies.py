"""FastAPI dependencies of the RAG module."""

from typing import Annotated, cast

from fastapi import Depends, Request

from app.core.config import settings_of
from app.llm.dependencies import LLMClientDep
from app.modules.rag.answers import Answerer, Grounding
from app.modules.rag.chunk_store import ChunkStore
from app.modules.rag.config import RagSettings
from app.modules.rag.embedder import Embedder
from app.modules.rag.index import ChunkIndex
from app.modules.rag.schemas import RagQuestion


async def get_embedder(request: Request) -> Embedder:
    """The embedder the module's lifespan created."""
    return cast(Embedder, request.app.state.rag_embedder)


async def get_chunk_store(request: Request) -> ChunkStore:
    """The chunk store the module's lifespan created."""
    return cast(ChunkStore, request.app.state.rag_chunk_store)


async def get_chunk_index(request: Request) -> ChunkIndex:
    """The service the endpoints call, on the lifespan's embedder and store. Tests override
    this."""
    return cast(ChunkIndex, request.app.state.rag_index)


ChunkIndexDep = Annotated[ChunkIndex, Depends(get_chunk_index)]


async def get_answerer(index: ChunkIndexDep, llm: LLMClientDep) -> Answerer:
    """The answerer, on this request's index and model, so tests' doubles reach it."""
    return Answerer(index, llm, min_similarity=settings_of(RagSettings).min_similarity)


AnswererDep = Annotated[Answerer, Depends(get_answerer)]


async def get_grounding(body: RagQuestion, answerer: AnswererDep) -> Grounding:
    """The question's sources, found before an answer streams, so a failure answers with its
    status rather than an event."""
    return await answerer.ground(body)


GroundingDep = Annotated[Grounding, Depends(get_grounding)]
