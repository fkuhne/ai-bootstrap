"""A deterministic embedder, for tests and for running the module without a model."""

import math
import re
import zlib
from collections.abc import Sequence

from app.modules.rag.embedder import Document, Embedder, Vector

DIMENSIONS = 64

WORD = re.compile(r"\w+")


class FakeEmbedder(Embedder):
    """Counts each word of a text in one of 64 dimensions, chosen by a hash of the word, so
    texts that share words come close, as texts that mean the same do with a real model.

    `RAG_PROVIDER=fake` selects it.
    """

    def __init__(self, *, ready: bool = True) -> None:
        self._ready = ready
        self.closed = False

    async def embed_documents(self, documents: Sequence[Document]) -> list[Vector]:
        return [_vector(f"{d.title or ''} {d.text}") for d in documents]

    async def embed_query(self, text: str) -> Vector:
        return _vector(text)

    async def is_ready(self) -> bool:
        return self._ready

    async def aclose(self) -> None:
        self.closed = True


def _vector(text: str) -> Vector:
    """The words' counts, scaled to length 1 as most models' vectors are."""
    vector = [0.0] * DIMENSIONS
    for word in WORD.findall(text.lower()):
        vector[zlib.crc32(word.encode()) % DIMENSIONS] += 1
    length = math.sqrt(sum(value * value for value in vector))
    return [value / length for value in vector] if length else vector
