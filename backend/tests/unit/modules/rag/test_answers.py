"""Answers from the chunks: the question, the prompt with numbered sources, and when the documents
can't ground an answer."""

import pytest
from pydantic import ValidationError

from app.llm.llm_client import ChatMessage, ImagePart, ImageURL, TextPart
from app.modules.rag.answers import INSTRUCTIONS, REFUSAL, Answerer, system_prompt
from app.modules.rag.chunks import Chunk
from app.modules.rag.fake_chunk_store import FakeChunkStore
from app.modules.rag.fake_embedder import FakeEmbedder
from app.modules.rag.index import ChunkIndex
from app.modules.rag.schemas import RagQuestion, RagSource
from app.openapi import schema
from tests.helpers import ScriptedLLM

pytestmark = pytest.mark.anyio

REFUNDS = Chunk(
    id="r", source="help/returns.md", title="Refunds", text="Refunds are paid back in a week."
)
PARCELS = Chunk(id="p", source="help/shipping.md", text="Parcels arrive in three days.")


def question(text: str = "When are refunds paid back?", **fields: object) -> RagQuestion:
    return RagQuestion.model_validate({"messages": [{"role": "user", "content": text}], **fields})


async def answerer(llm: ScriptedLLM, *, min_similarity: float | None = None) -> Answerer:
    index = ChunkIndex(FakeEmbedder(), FakeChunkStore(), model="local", collection="chunks")
    await index.store([REFUNDS, PARCELS])
    return Answerer(index, llm, min_similarity=min_similarity)


def test_the_question_is_the_last_message_the_user_s_with_text() -> None:
    parts = ChatMessage(
        role="user",
        content=[
            TextPart(type="text", text="What is this?"),
            ImagePart(type="image_url", image_url=ImageURL(url="data:image/png;base64,YQ==")),
        ],
    )

    assert RagQuestion(messages=[parts]).question == "What is this?"
    for last in (
        {"role": "assistant", "content": "Hello"},
        {"role": "user", "content": [{"type": "image_url", "image_url": {"url": "http://x/i"}}]},
    ):
        with pytest.raises(ValidationError, match="the last message must be the user's"):
            RagQuestion.model_validate({"messages": [last]})


def test_the_prompt_numbers_each_source_with_its_title_and_document() -> None:
    sources = [
        RagSource(number=1, chunk=REFUNDS, similarity=0.8),
        RagSource(number=2, chunk=PARCELS, similarity=0.3),
    ]

    assert system_prompt(sources) == (
        f"{INSTRUCTIONS}\n\nSources:\n\n"
        "[1] Refunds (help/returns.md)\nRefunds are paid back in a week.\n\n"
        "[2] help/shipping.md\nParcels arrive in three days."
    )


async def test_an_answer_gives_the_model_the_sources_then_the_conversation() -> None:
    llm = ScriptedLLM()
    asked = question(parameters={"seed": 7}, limit=2)

    answer = await (await answerer(llm)).answer(asked)

    assert (answer.content, answer.model, answer.refused) == ("Hello", "scripted", False)
    assert [source.number for source in answer.sources] == [1, 2]
    assert answer.sources[0].chunk == REFUNDS
    messages, parameters = llm.sent[0]
    assert [m.role for m in messages] == ["system", "user"]
    assert messages[0].content == system_prompt(answer.sources)
    assert parameters == {"seed": 7}


async def test_with_no_chunk_found_the_documents_don_t_say_and_the_model_isn_t_asked() -> None:
    llm = ScriptedLLM()
    empty = Answerer(
        ChunkIndex(FakeEmbedder(), FakeChunkStore(), model="local", collection="chunks"),
        llm,
        min_similarity=None,
    )

    answer = await empty.answer(question())

    assert (answer.content, answer.refused, answer.sources) == (REFUSAL, True, [])
    assert llm.sent == []


@pytest.mark.parametrize(("minimum", "refused"), [(0.99, True), (0.1, False)])
async def test_a_question_too_far_from_every_chunk_is_refused_when_a_minimum_is_set(
    minimum: float, refused: bool
) -> None:
    llm = ScriptedLLM()

    answer = await (await answerer(llm, min_similarity=minimum)).answer(question())

    assert answer.refused is refused
    # The chunks found are given either way, so the app can show how close they came.
    assert len(answer.sources) == 2
    assert (llm.sent == []) is refused


def test_the_published_example_is_a_valid_question() -> None:
    for example in schema()["components"]["schemas"]["RagQuestion"]["examples"]:
        RagQuestion.model_validate(example)
