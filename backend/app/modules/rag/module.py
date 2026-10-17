"""The RAG module, as the core plugs it in (docs/foundations.md#rag)."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.core.config import settings_of
from app.core.modules import Module
from app.modules.rag.config import RagSettings
from app.modules.rag.dependencies import get_chunk_store, get_embedder
from app.modules.rag.factory import create_chunk_store, create_embedder
from app.modules.rag.index import ChunkIndex
from app.modules.rag.router import router
from app.modules.rag.schemas import RagDoneEvent, RagSourcesEvent

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create the embedder and the chunk store when the app starts, and close them when it
    stops."""
    settings = settings_of(RagSettings)
    embedder = create_embedder(settings)
    chunk_store = create_chunk_store(settings)
    if settings.provider == "fake":
        logger.info("RAG with the fake embedder and chunk store.")
    else:
        logger.info(
            "RAG with the embedding model %r at %s, and Qdrant at %s.",
            settings.embedding_model,
            settings.embedding_base_url,
            settings.qdrant_url,
        )
    app.state.rag_embedder = embedder
    app.state.rag_chunk_store = chunk_store
    app.state.rag_index = ChunkIndex(
        embedder, chunk_store, model=settings.embedding_model, collection=settings.collection
    )
    try:
        yield
    finally:
        await embedder.aclose()
        await chunk_store.aclose()


async def is_ready(request: Request) -> bool:
    """Ready when both the embedding model and the store are."""
    embedder = await get_embedder(request)
    chunk_store = await get_chunk_store(request)
    return await embedder.is_ready() and await chunk_store.is_ready()


MODULE = Module(
    name="rag",
    router=router,
    settings=RagSettings,
    lifespan=lifespan,
    is_ready=is_ready,
    event_models=(RagSourcesEvent, RagDoneEvent),
)
