"""The RAG module's API: what its endpoints take, answer and stream, around the chunk and the
search's hits (docs/foundations.md#rag)."""

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.llm.llm_client import ChatMessage, RequestParameters, Usage, text_of
from app.modules.rag.chunks import Chunk, Hit, Mode, SourceSummary

# The most chunks one request stores; an app stores more in several.
MAX_CHUNKS = 1000


# The most hits a search returns.
MAX_HITS = 50


class StoreRequest(BaseModel):
    """Chunks to store, each replacing any stored before under its id."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "chunks": [
                        {
                            "id": "returns-1",
                            "source": "help/returns.md",
                            "title": "Returns",
                            "text": "Items can be returned within 30 days, unused.",
                            "metadata": {"page": 1},
                        }
                    ]
                }
            ]
        }
    )

    chunks: list[Chunk] = Field(min_length=1, max_length=MAX_CHUNKS)

    @model_validator(mode="after")
    def _ids_are_unique(self) -> StoreRequest:
        ids = [chunk.id for chunk in self.chunks]
        if len(set(ids)) < len(ids):
            raise ValueError("each chunk's id must be unique in the request")
        return self


class Stored(BaseModel):
    """How many chunks were stored."""

    stored: int


class Deleted(BaseModel):
    """How many chunks were deleted."""

    deleted: int


class SourceList(BaseModel):
    """The sources stored, by name."""

    sources: list[SourceSummary]


class SearchRequest(BaseModel):
    """A question, and how to search for it."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"query": "How long do refunds take?", "limit": 5}]}
    )

    query: str = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=MAX_HITS)
    mode: Mode = Field(
        default="hybrid",
        description="`hybrid`, by meaning and words fused by rank; `dense`, by meaning alone; "
        "`words`, by BM25 alone.",
    )
    sources: list[str] | None = Field(
        default=None, min_length=1, description="Only these sources' chunks, if given."
    )


class SearchResult(BaseModel):
    """The chunks found."""

    hits: list[Hit]


# The most chunks an answer is given.
MAX_SOURCES = 20


class RagQuestion(BaseModel):
    """A conversation whose last message, the user's, is the question: the stored chunks are
    searched for it, and the best ones given to the model with the conversation."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "messages": [{"role": "user", "content": "How long do refunds take?"}],
                    "parameters": {"reasoning_effort": "none"},
                    "limit": 5,
                }
            ]
        }
    )

    messages: list[ChatMessage] = Field(min_length=1)
    parameters: RequestParameters = Field(default_factory=dict)
    limit: int = Field(
        default=5, ge=1, le=MAX_SOURCES, description="How many chunks to answer from."
    )
    sources: list[str] | None = Field(
        default=None, min_length=1, description="Only these sources' chunks, if given."
    )

    @model_validator(mode="after")
    def _ends_with_a_question(self) -> RagQuestion:
        last = self.messages[-1]
        if last.role != "user" or not text_of(last.content).strip():
            raise ValueError("the last message must be the user's, with text: the question")
        return self

    @property
    def question(self) -> str:
        return text_of(self.messages[-1].content)


class RagSource(BaseModel):
    """A chunk the model was given to answer from, by the number it cites it with."""

    number: int
    chunk: Chunk
    similarity: float = Field(description="How close its meaning is to the question's.")


class RagAnswer(BaseModel):
    """The answer, and the sources it was given."""

    sources: list[RagSource]
    content: str
    reasoning: str | None = None
    model: str | None = Field(default=None, description="None when the model wasn't asked.")
    finish_reason: str | None = None
    usage: Usage | None = None
    refused: bool = Field(
        description="True when the documents couldn't ground an answer, and the model wasn't "
        "asked: no chunk was found, or none as similar as RAG_MIN_SIMILARITY asks."
    )


class RagSourcesEvent(BaseModel):
    """Data of the `sources` event, which comes first: the chunks given to the model."""

    sources: list[RagSource]


class RagDoneEvent(BaseModel):
    """Data of the `done` event: how the answer ended."""

    model: str | None = None
    finish_reason: str | None = None
    usage: Usage | None = None
    refused: bool
