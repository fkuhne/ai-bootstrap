"""A chunk store in memory, for tests and for running the module without Qdrant."""

import re
from collections import Counter, defaultdict
from collections.abc import Callable, Sequence

from app.modules.rag.chunk_store import (
    ChunkStore,
    Found,
    ModelIdentity,
    Query,
    StoredChunk,
    cosine,
)
from app.modules.rag.chunks import SourceSummary

WORD = re.compile(r"\w+")

# RRF's constant, Qdrant's own.
RRF_K = 2


class FakeChunkStore(ChunkStore):
    """Keeps the chunks in a dictionary, by id, for as long as the process runs; ready unless
    told otherwise. It searches as Qdrant does, roughly: by meaning, the vectors' cosine; by
    words, how many of the question's a chunk holds; hybrid, both fused by rank.

    `RAG_PROVIDER=fake` selects it.
    """

    def __init__(self, *, ready: bool = True) -> None:
        self._ready = ready
        self.closed = False
        self.made_for: ModelIdentity | None = None
        self.chunks: dict[str, StoredChunk] = {}

    async def identity(self) -> ModelIdentity | None:
        return self.made_for

    async def create(self, identity: ModelIdentity) -> None:
        self.made_for = identity

    async def upsert(self, chunks: Sequence[StoredChunk]) -> None:
        self.chunks.update((stored.chunk.id, stored) for stored in chunks)

    async def delete_source(self, source: str) -> int:
        gone = [id_ for id_, stored in self.chunks.items() if stored.chunk.source == source]
        for id_ in gone:
            del self.chunks[id_]
        return len(gone)

    async def sources(self) -> list[SourceSummary]:
        counts = Counter(stored.chunk.source for stored in self.chunks.values())
        return [SourceSummary(source=source, chunks=counts[source]) for source in sorted(counts)]

    async def search(self, query: Query) -> list[Found]:
        pool = [
            stored
            for stored in self.chunks.values()
            if query.sources is None or stored.chunk.source in query.sources
        ]
        meaning = _ranked(pool, lambda stored: cosine(query.vector, stored.vector))
        asked = set(WORD.findall(query.text.lower()))
        words = [
            (stored, score)
            for stored, score in _ranked(pool, lambda stored: len(asked & _words(stored)))
            if score > 0
        ]
        if query.mode == "dense":
            ranked = meaning
        elif query.mode == "words":
            ranked = words
        else:
            fused: defaultdict[str, float] = defaultdict(float)
            for half in (meaning, words):
                for rank, (stored, _score) in enumerate(half, start=1):
                    fused[stored.chunk.id] += 1 / (RRF_K + rank)
            ranked = _ranked(pool, lambda stored: fused[stored.chunk.id])
        return [Found(stored.chunk, score, stored.vector) for stored, score in ranked][
            : query.limit
        ]

    async def is_ready(self) -> bool:
        return self._ready

    async def aclose(self) -> None:
        self.closed = True


def _ranked(
    pool: list[StoredChunk], score: Callable[[StoredChunk], float]
) -> list[tuple[StoredChunk, float]]:
    """The chunks by their score, best first; a tie keeps the order they were stored in."""
    scored = [(stored, score(stored)) for stored in pool]
    return sorted(scored, key=lambda pair: -pair[1])


def _words(stored: StoredChunk) -> set[str]:
    return set(WORD.findall(f"{stored.chunk.title or ''} {stored.chunk.text}".lower()))
