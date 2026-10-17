"""Answers from an app's chunks: the best chunks for the question, numbered, given to the model
before the caller's messages, and its answer, citing them by number (docs/foundations.md#rag).
The prompt is the template's: an app adapts it to its own documents."""

from collections.abc import AsyncGenerator, Sequence
from dataclasses import dataclass

from app.llm.llm_client import (
    ChatMessage,
    LLMClient,
    StreamPart,
)
from app.modules.rag.chunks import Chunk
from app.modules.rag.index import ChunkIndex
from app.modules.rag.schemas import RagAnswer, RagQuestion, RagSource

# The answer when the documents can't ground one: no chunk found, or none similar enough.
REFUSAL = "The documents don't say."

INSTRUCTIONS = (
    "Answer the user's question from the sources below, and from nothing else. Cite each "
    "source you use by its number in square brackets, such as [1], right after what it "
    "supports. If the sources don't answer the question, say so, and don't guess."
)


@dataclass(frozen=True)
class Grounding:
    """A question, its sources, and whether they can ground an answer."""

    question: RagQuestion
    sources: list[RagSource]
    refused: bool


class Answerer:
    """Grounds a question in the stored chunks, then asks the model, unless they can't."""

    def __init__(self, index: ChunkIndex, llm: LLMClient, *, min_similarity: float | None) -> None:
        self._index = index
        self._llm = llm
        self._min_similarity = min_similarity

    async def ground(self, question: RagQuestion) -> Grounding:
        hits = await self._index.search(
            question.question, limit=question.limit, sources=question.sources
        )
        sources = [
            RagSource(number=number, chunk=hit.chunk, similarity=hit.similarity)
            for number, hit in enumerate(hits, start=1)
        ]
        best = max((source.similarity for source in sources), default=None)
        refused = best is None or (self._min_similarity is not None and best < self._min_similarity)
        return Grounding(question, sources, refused)

    async def answer(self, question: RagQuestion) -> RagAnswer:
        grounding = await self.ground(question)
        if grounding.refused:
            return RagAnswer(sources=grounding.sources, content=REFUSAL, refused=True)
        completion = await self._llm.complete(
            messages_for(grounding), parameters=question.parameters
        )
        return RagAnswer(
            sources=grounding.sources,
            content=completion.content,
            reasoning=completion.reasoning,
            model=completion.model,
            finish_reason=completion.finish_reason,
            usage=completion.usage,
            refused=False,
        )

    def stream(self, grounding: Grounding) -> AsyncGenerator[StreamPart]:
        """The model's answer to a question that can be grounded, piece by piece."""
        return self._llm.stream(messages_for(grounding), parameters=grounding.question.parameters)


def messages_for(grounding: Grounding) -> list[ChatMessage]:
    """The sources and the instructions, then the caller's own messages."""
    return [
        ChatMessage(role="system", content=system_prompt(grounding.sources)),
        *grounding.question.messages,
    ]


def system_prompt(sources: Sequence[RagSource]) -> str:
    """The instructions, then each source by its number, its title and its document."""
    blocks = [
        f"[{source.number}] {_heading(source.chunk)}\n{source.chunk.text}" for source in sources
    ]
    return INSTRUCTIONS + "\n\nSources:\n\n" + "\n\n".join(blocks)


def _heading(chunk: Chunk) -> str:
    return f"{chunk.title} ({chunk.source})" if chunk.title else chunk.source
