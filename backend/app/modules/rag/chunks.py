"""The chunk, as an app stores it, and what a search finds (docs/foundations.md#rag). The
endpoints' own models are in `schemas.py`."""

from typing import Literal

from pydantic import BaseModel, Field, JsonValue

# How a search ranks: by meaning and words fused, by meaning alone, or by words alone.
Mode = Literal["hybrid", "dense", "words"]


class Chunk(BaseModel):
    """A piece of an app's document, as the app cut it."""

    id: str = Field(
        min_length=1,
        description="The app's own id for the chunk. Storing it again replaces it.",
    )
    source: str = Field(
        min_length=1,
        description="The document it came from: answers cite it, and a source's chunks are "
        "deleted together.",
    )
    text: str = Field(min_length=1, description="What's embedded and searched.")
    title: str | None = Field(
        default=None,
        description="A title, such as its section's, embedded and searched with the text.",
    )
    metadata: dict[str, JsonValue] = Field(
        default_factory=dict, description="Anything the app keeps with it, returned as given."
    )


class SourceSummary(BaseModel):
    """A source, and how many of its chunks are stored."""

    source: str
    chunks: int


class Hit(BaseModel):
    """A chunk found, best first."""

    chunk: Chunk
    score: float = Field(
        description="Its score in the search's mode: its fused rank's in hybrid, its similarity "
        "in dense, its BM25 weight in words. Comparable within one search only."
    )
    similarity: float = Field(
        description="How close its meaning is to the question's: the cosine of their vectors, "
        "whatever the mode. It depends on the embedding model."
    )
