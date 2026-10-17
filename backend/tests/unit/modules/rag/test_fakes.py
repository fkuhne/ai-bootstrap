"""The fakes stand in for the embedding model and Qdrant, in tests and with RAG_PROVIDER=fake."""

import math

import pytest

from app.modules.rag.chunk_store import Query, StoredChunk
from app.modules.rag.chunks import Chunk, Mode
from app.modules.rag.embedder import Document, Vector
from app.modules.rag.fake_chunk_store import FakeChunkStore
from app.modules.rag.fake_embedder import DIMENSIONS, FakeEmbedder

pytestmark = pytest.mark.anyio


def similarity(a: Vector, b: Vector) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


async def test_the_fake_embedder_brings_texts_with_shared_words_close() -> None:
    embedder = FakeEmbedder()
    question = await embedder.embed_query("How are refunds handled?")
    billing, tyres = await embedder.embed_documents(
        [
            Document("Refunds are handled by the billing team."),
            Document("Change a flat tyre with two levers."),
        ]
    )

    assert similarity(question, billing) > similarity(question, tyres)
    assert len(question) == DIMENSIONS
    assert math.isclose(math.hypot(*billing), 1)
    # The same text, the same vector, from either method.
    assert await embedder.embed_query("Refunds are handled by the billing team.") == billing


async def test_the_fake_embedder_gives_a_text_without_words_a_zero_vector() -> None:
    assert await FakeEmbedder().embed_query("?!") == [0.0] * DIMENSIONS


@pytest.mark.parametrize("fake", [FakeEmbedder, FakeChunkStore])
async def test_the_fakes_are_ready_unless_told_otherwise_and_record_closing(
    fake: type[FakeEmbedder] | type[FakeChunkStore],
) -> None:
    ready, not_ready = fake(), fake(ready=False)

    assert await ready.is_ready() is True
    assert await not_ready.is_ready() is False

    await ready.aclose()

    assert ready.closed


async def stored(embedder: FakeEmbedder, *chunks: Chunk) -> FakeChunkStore:
    store = FakeChunkStore()
    vectors = await embedder.embed_documents([Document(c.text, c.title) for c in chunks])
    await store.upsert([StoredChunk(c, v) for c, v in zip(chunks, vectors, strict=True)])
    return store


REFUNDS = Chunk(id="r", source="help/returns.md", text="Refunds are paid back within a week.")
CODE = Chunk(id="e", source="help/errors.md", text="Error code E-4012 means a declined card.")
PARCELS = Chunk(id="p", source="help/shipping.md", text="Parcels arrive in three days.")


@pytest.mark.parametrize(
    ("mode", "text", "first"),
    [
        ("dense", "When are refunds paid back?", "r"),
        ("words", "E-4012", "e"),
        ("hybrid", "E-4012", "e"),
        ("hybrid", "When are refunds paid back?", "r"),
    ],
)
async def test_the_fake_store_searches_by_meaning_by_words_or_both(
    mode: Mode, text: str, first: str
) -> None:
    embedder = FakeEmbedder()
    store = await stored(embedder, REFUNDS, CODE, PARCELS)
    query = Query(text, await embedder.embed_query(text), 3, mode)

    found = await store.search(query)

    assert found[0].chunk.id == first


async def test_the_fake_store_finds_by_words_only_chunks_holding_them_and_keeps_sources() -> None:
    embedder = FakeEmbedder()
    store = await stored(embedder, REFUNDS, CODE, PARCELS)
    vector = await embedder.embed_query("E-4012")

    by_words = await store.search(Query("E-4012", vector, 3, "words"))
    kept = await store.search(Query("E-4012", vector, 1, "hybrid", ("help/shipping.md",)))

    assert [f.chunk.id for f in by_words] == ["e"]
    assert [f.chunk.id for f in kept] == ["p"]
