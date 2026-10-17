"""The embedder port: texts in, vectors for their meaning out (docs/foundations.md#rag)."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

# A text's meaning as numbers: texts that mean the same have vectors close together.
Vector = list[float]


@dataclass(frozen=True)
class Document:
    """A chunk's text to embed, with its title if it has one."""

    text: str
    title: str | None = None


class Embedder(Protocol):
    """An embedding model the backend can call. Implementations are interchangeable
    (Strategy).

    Chunks and questions are embedded by separate methods, since a model may want each
    written its own way. Every method raises the core's `ServiceError`s on failure.
    """

    async def embed_documents(self, documents: Sequence[Document]) -> list[Vector]:
        """One vector per chunk, in the same order."""
        ...

    async def embed_query(self, text: str) -> Vector:
        """The vector of a question, to search the chunks with."""
        ...

    async def is_ready(self) -> bool:
        """Tell whether the model can take requests right now."""
        ...

    async def aclose(self) -> None:
        """Release connections and other resources."""
        ...
