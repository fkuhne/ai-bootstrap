"""The module's service, on the fakes: chunks embedded in batches, with their titles, kept in a
collection made on the first store for the embedding model, and refused for another; and a
search, with each hit's similarity, checked against the same model."""

from collections.abc import Sequence

import pytest

from app.modules.rag.chunk_store import ModelIdentity, cosine
from app.modules.rag.chunks import Chunk, SourceSummary
from app.modules.rag.embedder import Document, Vector
from app.modules.rag.exceptions import RagModelChangedError
from app.modules.rag.fake_chunk_store import FakeChunkStore
from app.modules.rag.fake_embedder import FakeEmbedder
from app.modules.rag.index import BATCH, PROBE, ChunkIndex

pytestmark = pytest.mark.anyio


class RecordingEmbedder(FakeEmbedder):
    """The fake, keeping each call's documents."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[list[Document]] = []

    async def embed_documents(self, documents: Sequence[Document]) -> list[Vector]:
        self.calls.append(list(documents))
        return await super().embed_documents(documents)


class OtherModel(FakeEmbedder):
    """Another model of the same size: its vectors point elsewhere."""

    async def embed_documents(self, documents: Sequence[Document]) -> list[Vector]:
        return [list(reversed(vector)) for vector in await super().embed_documents(documents)]


def chunk(number: int, source: str = "help/returns.md") -> Chunk:
    return Chunk(id=f"c{number}", source=source, title=f"Part {number}", text=f"Text {number}.")


async def test_the_first_store_makes_the_collection_for_the_model() -> None:
    store = FakeChunkStore()
    embedder = FakeEmbedder()
    index = ChunkIndex(embedder, store, model="local", collection="chunks")

    assert await index.store([chunk(1)]) == 1

    assert store.made_for is not None
    assert store.made_for.model == "local"
    assert store.made_for.probe == (await embedder.embed_documents([PROBE]))[0]
    assert store.made_for.dimensions == len(store.made_for.probe)
    assert list(store.chunks) == ["c1"]


async def test_chunks_are_embedded_in_batches_with_their_titles() -> None:
    embedder = RecordingEmbedder()
    index = ChunkIndex(embedder, FakeChunkStore(), model="local", collection="chunks")

    await index.store([chunk(number) for number in range(BATCH + 2)])

    # The probe, then a full batch, then the rest.
    assert [len(call) for call in embedder.calls] == [1, BATCH, 2]
    assert embedder.calls[1][0] == Document("Text 0.", "Part 0")


async def test_the_same_model_stores_again_and_a_chunk_s_id_replaces_it() -> None:
    store = FakeChunkStore()
    index = ChunkIndex(FakeEmbedder(), store, model="local", collection="chunks")
    await index.store([chunk(1)])

    await index.store([chunk(1).model_copy(update={"text": "Changed."})])

    assert [stored.chunk.text for stored in store.chunks.values()] == ["Changed."]


async def test_another_model_is_refused_with_what_to_do() -> None:
    store = FakeChunkStore()
    await ChunkIndex(FakeEmbedder(), store, model="local", collection="chunks").store([chunk(1)])
    other = ChunkIndex(OtherModel(), store, model="local", collection="chunks")

    with pytest.raises(RagModelChangedError) as refused:
        await other.store([chunk(2)])

    assert "The collection 'chunks' holds another embedding model's vectors" in str(refused.value)
    assert "set RAG_COLLECTION to another name" in str(refused.value)
    assert list(store.chunks) == ["c1"]


async def test_sources_are_listed_and_deleted_through_the_store() -> None:
    store = FakeChunkStore()
    index = ChunkIndex(FakeEmbedder(), store, model="local", collection="chunks")
    await index.store([chunk(1), chunk(2), chunk(3, source="help/shipping.md")])

    assert await index.sources() == [
        SourceSummary(source="help/returns.md", chunks=2),
        SourceSummary(source="help/shipping.md", chunks=1),
    ]
    assert await index.delete_source("help/returns.md") == 2
    assert await index.sources() == [SourceSummary(source="help/shipping.md", chunks=1)]
    assert await index.delete_source("help/returns.md") == 0


class CountingStore(FakeChunkStore):
    """The fake, counting how often the collection's model is asked."""

    def __init__(self) -> None:
        super().__init__()
        self.asked = 0

    async def identity(self) -> ModelIdentity | None:
        self.asked += 1
        return await super().identity()


async def test_a_search_finds_chunks_with_their_similarity_to_the_question() -> None:
    embedder = FakeEmbedder()
    index = ChunkIndex(embedder, FakeChunkStore(), model="local", collection="chunks")
    await index.store([chunk(1), chunk(2, source="help/shipping.md")])

    hits = await index.search("Part 2 text", limit=2, mode="words", sources=["help/shipping.md"])

    assert [hit.chunk.id for hit in hits] == ["c2"]
    question = await embedder.embed_query("Part 2 text")
    stored = (await embedder.embed_documents([Document("Text 2.", "Part 2")]))[0]
    assert hits[0].similarity == pytest.approx(cosine(question, stored))


async def test_a_search_checks_the_model_once_and_without_a_collection_finds_nothing() -> None:
    store = CountingStore()
    index = ChunkIndex(FakeEmbedder(), store, model="local", collection="chunks")

    assert await index.search("anything", limit=5) == []
    assert store.made_for is None  # a search makes no collection
    await index.store([chunk(1)])
    await index.search("anything", limit=5)
    await index.search("anything", limit=5)

    # Once for the empty search, once for the store; the searches after reuse the check.
    assert store.asked == 2


async def test_a_search_with_another_model_is_refused() -> None:
    store = FakeChunkStore()
    await ChunkIndex(FakeEmbedder(), store, model="local", collection="chunks").store([chunk(1)])

    with pytest.raises(RagModelChangedError):
        await ChunkIndex(OtherModel(), store, model="local", collection="chunks").search(
            "anything", limit=5
        )
