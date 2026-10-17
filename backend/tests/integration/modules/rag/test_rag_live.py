"""Live checks against the configured embedding model and Qdrant. Excluded by default; run
them with:

    docker compose up -d --wait
    docker compose run --rm backend-checks pytest -m integration --no-cov -k rag_live

`RAG_EMBEDDING_BASE_URL`, `RAG_EMBEDDING_MODEL`, `RAG_EMBEDDING_API_KEY` and `RAG_QDRANT_URL`
point them elsewhere.
"""

import uuid

import httpx2
import pytest

from app.core.errors import ServiceError
from app.llm.config import LLMSettings
from app.llm.factory import create_llm_client
from app.modules.rag.answers import Answerer
from app.modules.rag.chunks import Chunk, SourceSummary
from app.modules.rag.config import RagSettings
from app.modules.rag.embedder import Document
from app.modules.rag.factory import create_chunk_store, create_embedder
from app.modules.rag.index import ChunkIndex
from app.modules.rag.schemas import RagQuestion

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


async def test_the_configured_embedding_model_embeds_chunks_and_questions() -> None:
    embedder = create_embedder(RagSettings())
    try:
        assert await embedder.is_ready()

        chunks = await embedder.embed_documents(
            [
                Document("Refunds are handled by the billing team.", "Refunds"),
                Document("Parcels arrive within three days."),
            ]
        )
        question = await embedder.embed_query("How do I get my money back?")

        # One vector per text, all of the model's size: this tests the integration, not the
        # model.
        assert len(chunks) == 2
        assert len({len(vector) for vector in [*chunks, question]}) == 1
        assert chunks[0] != chunks[1]
    finally:
        await embedder.aclose()


async def test_a_text_too_long_is_refused_with_the_provider_s_reason() -> None:
    settings = RagSettings()
    if settings.provider == "fake":
        pytest.skip("the fake embeds any length")
    embedder = create_embedder(settings)
    try:
        with pytest.raises(ServiceError, match="status"):
            await embedder.embed_query("refund " * 50_000)
    finally:
        await embedder.aclose()


async def test_the_configured_qdrant_is_ready() -> None:
    store = create_chunk_store(RagSettings())
    try:
        assert await store.is_ready()
    finally:
        await store.aclose()


async def test_chunks_are_stored_listed_replaced_and_deleted_in_a_collection_of_their_own() -> None:
    # A collection of the test's own, deleted after, so an app's chunks are never touched.
    settings = RagSettings(collection=f"live-test-{uuid.uuid4().hex[:8]}")
    embedder = create_embedder(settings)
    store = create_chunk_store(settings)
    index = ChunkIndex(
        embedder, store, model=settings.embedding_model, collection=settings.collection
    )
    returns = Chunk(id="r1", source="help/returns.md", title="Returns", text="Within 30 days.")
    try:
        assert await index.store([returns, returns.model_copy(update={"id": "r2"})]) == 2
        assert await index.store([returns.model_copy(update={"text": "Changed."})]) == 1

        assert await index.sources() == [SourceSummary(source="help/returns.md", chunks=2)]
        assert await index.delete_source("help/returns.md") == 2
        assert await index.sources() == []
    finally:
        await _drop(settings)
        await embedder.aclose()
        await store.aclose()


async def _drop(settings: RagSettings) -> None:
    if settings.provider == "fake":
        return
    async with httpx2.AsyncClient(base_url=str(settings.qdrant_url)) as http:
        await http.delete(f"collections/{settings.collection}")


SAMPLES = [
    Chunk(
        id="r", source="live/returns.md", title="Refunds", text="Refunds are paid back in a week."
    ),
    Chunk(id="e", source="live/errors.md", text="Error code E-4012 means the card was declined."),
    Chunk(id="p", source="live/shipping.md", text="Parcels arrive within three working days."),
]


async def test_a_search_finds_an_exact_code_by_its_words_and_the_model_answers_from_it() -> None:
    settings = RagSettings(collection=f"live-test-{uuid.uuid4().hex[:8]}")
    embedder = create_embedder(settings)
    store = create_chunk_store(settings)
    llm = create_llm_client(LLMSettings())
    index = ChunkIndex(
        embedder, store, model=settings.embedding_model, collection=settings.collection
    )
    try:
        await index.store(SAMPLES)

        # By its words, an exact code comes first, alone or fused: this tests the integration,
        # not the embedding model.
        for mode in ("words", "hybrid"):
            hits = await index.search("E-4012", limit=3, mode=mode)
            assert hits[0].chunk.id == "e", mode
        dense = await index.search("When are refunds paid back?", limit=3, mode="dense")
        assert len(dense) == 3
        assert all(-1 <= hit.similarity <= 1 for hit in dense)

        question = RagQuestion.model_validate(
            {
                "messages": [{"role": "user", "content": "What does E-4012 mean?"}],
                "parameters": {"max_tokens": 512},
                "limit": 2,
            }
        )
        answer = await Answerer(index, llm, min_similarity=None).answer(question)
        assert not answer.refused
        assert answer.sources[0].chunk.id == "e"
        assert (answer.content or answer.reasoning or "").strip()
    finally:
        await _drop(settings)
        await embedder.aclose()
        await store.aclose()
        await llm.aclose()
