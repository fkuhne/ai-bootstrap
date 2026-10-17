"""The chunk store port: where the chunks and their vectors are kept (docs/foundations.md#rag)."""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from app.modules.rag.chunks import Chunk, Mode, SourceSummary
from app.modules.rag.embedder import Vector

# How alike two probe vectors must be to come from one model: the same model gives the same
# vector, give or take rounding between machines; another model's is unrelated.
SAME_MODEL = 0.99


@dataclass(frozen=True)
class ModelIdentity:
    """The embedding model a collection's vectors come from: its configured name, its vectors'
    size, and its vector for a fixed probe text. The name alone proves nothing, since llama.cpp's
    server answers to any name; the probe tells one model from another."""

    model: str
    dimensions: int
    probe: Vector

    def same_model(self, other: ModelIdentity) -> bool:
        return self.dimensions == other.dimensions and cosine(self.probe, other.probe) >= SAME_MODEL


@dataclass(frozen=True)
class StoredChunk:
    """A chunk, and the vector of its meaning."""

    chunk: Chunk
    vector: Vector


@dataclass(frozen=True)
class Query:
    """A search: the question's text, for its words, and its vector, for its meaning."""

    text: str
    vector: Vector
    limit: int
    mode: Mode
    # Only these sources' chunks, if given.
    sources: tuple[str, ...] | None = None


@dataclass(frozen=True)
class Found:
    """A chunk found, with its score in the search's mode, and its vector."""

    chunk: Chunk
    score: float
    vector: Vector


class ChunkStore(Protocol):
    """A store the backend can call. Implementations are interchangeable (Strategy).

    Every method raises the core's `ServiceError`s on failure.
    """

    async def identity(self) -> ModelIdentity | None:
        """The model the collection was made for; None while there's no collection."""
        ...

    async def create(self, identity: ModelIdentity) -> None:
        """Make the collection, for the model's vectors."""
        ...

    async def upsert(self, chunks: Sequence[StoredChunk]) -> None:
        """Keep the chunks, each replacing any kept before under its id."""
        ...

    async def delete_source(self, source: str) -> int:
        """Remove a source's chunks, and say how many there were."""
        ...

    async def sources(self) -> list[SourceSummary]:
        """Each source kept, by name, and its number of chunks."""
        ...

    async def search(self, query: Query) -> list[Found]:
        """The chunks that best match, best first; none while there's no collection."""
        ...

    async def is_ready(self) -> bool:
        """Tell whether the store can take requests right now."""
        ...

    async def aclose(self) -> None:
        """Release connections and other resources."""
        ...


def cosine(a: Vector, b: Vector) -> float:
    """How alike two vectors point: 1 the same way, 0 unrelated, -1 opposite."""
    norms = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return sum(x * y for x, y in zip(a, b, strict=True)) / norms if norms else 0.0
