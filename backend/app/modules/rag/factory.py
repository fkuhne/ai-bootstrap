"""Builds the embedder and the chunk store the settings ask for (Factory)."""

import httpx2
from openai import AsyncOpenAI

from app.modules.rag.chunk_store import ChunkStore
from app.modules.rag.config import RagSettings
from app.modules.rag.embedder import Embedder
from app.modules.rag.fake_chunk_store import FakeChunkStore
from app.modules.rag.fake_embedder import FakeEmbedder
from app.modules.rag.openai_compatible_embedder import OpenAICompatibleEmbedder
from app.modules.rag.qdrant_chunk_store import QdrantChunkStore


def create_embedder(
    settings: RagSettings, *, http_client: httpx2.AsyncClient | None = None
) -> Embedder:
    """The fake, or a client of an OpenAI-compatible API. Tests pass an `http_client` with a
    mock transport, so no request leaves the process."""
    if settings.provider == "fake":
        return FakeEmbedder()
    sdk = AsyncOpenAI(
        base_url=str(settings.embedding_base_url),
        api_key=settings.embedding_api_key.get_secret_value(),
        timeout=settings.timeout_seconds,
        max_retries=0,
        http_client=http_client,
    )
    return OpenAICompatibleEmbedder(
        sdk,
        model=settings.embedding_model,
        query_format=settings.query_format,
        document_format=settings.document_format,
    )


def create_chunk_store(
    settings: RagSettings, *, transport: httpx2.AsyncBaseTransport | None = None
) -> ChunkStore:
    """The fake, or a Qdrant client. Tests pass a mock `transport`."""
    if settings.provider == "fake":
        return FakeChunkStore()
    key = settings.qdrant_api_key
    http = httpx2.AsyncClient(
        base_url=str(settings.qdrant_url),
        # Qdrant Cloud, or a Qdrant with a key, reads it from this header.
        headers={"api-key": key.get_secret_value()} if key else {},
        timeout=settings.timeout_seconds,
        transport=transport,
    )
    bm25 = {
        name: value
        for name, value in (
            ("language", settings.bm25_language),
            ("avg_len", settings.bm25_avg_len),
        )
        if value is not None
    }
    return QdrantChunkStore(http, collection=settings.collection, bm25=bm25)
