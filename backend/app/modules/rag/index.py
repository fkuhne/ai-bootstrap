"""Storing an app's chunks: each embedded, then kept with its BM25 weights, in a collection made
for the embedding model on the first store (docs/foundations.md#rag)."""

from collections.abc import Sequence

from app.modules.rag.chunk_store import ChunkStore, ModelIdentity, Query, StoredChunk, cosine
from app.modules.rag.chunks import Chunk, Hit, Mode, SourceSummary
from app.modules.rag.embedder import Document, Embedder
from app.modules.rag.exceptions import RagModelChangedError

# The text whose vector tells one embedding model from another.
PROBE = Document("A probe of the embedding model, whose vector tells one model from another.")

# How many chunks are embedded and kept at a time.
BATCH = 32


class ChunkIndex:
    """The module's service: what the endpoints call. It embeds, and the store keeps."""

    def __init__(
        self, embedder: Embedder, store: ChunkStore, *, model: str, collection: str
    ) -> None:
        self._embedder = embedder
        self._store = store
        self._model = model
        self._collection = collection
        # Whether the collection's model was checked while the backend runs: a store checks it
        # each time, a search once.
        self._checked = False

    async def store(self, chunks: Sequence[Chunk]) -> int:
        """Embed and keep the chunks, in batches; say how many."""
        await self._check(create=True)
        for start in range(0, len(chunks), BATCH):
            batch = chunks[start : start + BATCH]
            vectors = await self._embedder.embed_documents(
                [Document(chunk.text, chunk.title) for chunk in batch]
            )
            await self._store.upsert(
                [StoredChunk(chunk, vector) for chunk, vector in zip(batch, vectors, strict=True)]
            )
        return len(chunks)

    async def search(
        self,
        text: str,
        *,
        limit: int,
        mode: Mode = "hybrid",
        sources: Sequence[str] | None = None,
    ) -> list[Hit]:
        """The chunks that best match the question, best first, each with its similarity to
        it. The question is embedded by the model the collection was made for, or refused."""
        if not self._checked:
            await self._check(create=False)
        vector = await self._embedder.embed_query(text)
        found = await self._store.search(
            Query(text, vector, limit, mode, tuple(sources) if sources else None)
        )
        return [
            Hit(chunk=f.chunk, score=f.score, similarity=cosine(vector, f.vector)) for f in found
        ]

    async def delete_source(self, source: str) -> int:
        return await self._store.delete_source(source)

    async def sources(self) -> list[SourceSummary]:
        return await self._store.sources()

    async def _check(self, *, create: bool) -> None:
        """Check the collection was made for this model, or, to store, make it for it. Without
        a collection, a search has nothing to check, and finds nothing."""
        (probe,) = await self._embedder.embed_documents([PROBE])
        current = ModelIdentity(self._model, len(probe), probe)
        made_for = await self._store.identity()
        if made_for is None:
            if create:
                await self._store.create(current)
                self._checked = True
            return
        if not made_for.same_model(current):
            raise RagModelChangedError(
                f"The collection {self._collection!r} holds another embedding model's vectors "
                f"({made_for.model!r}, {made_for.dimensions} dimensions); this one is "
                f"{current.model!r}, with {current.dimensions}. Delete the collection, or set "
                "RAG_COLLECTION to another name, then store the chunks again."
            )
        self._checked = True
