import pytest

from app.llm.fake_llm_client import FakeLLMClient
from app.llm.llm_client import (
    ChatMessage,
    ContentDelta,
    ImagePart,
    ImageURL,
    ModelInfo,
    StreamEnd,
    TextPart,
    Usage,
)

pytestmark = pytest.mark.anyio

MESSAGES = [
    ChatMessage(role="system", content="Be brief."),
    ChatMessage(role="user", content="What is an LLM?"),
]


async def test_complete_answers_the_last_user_message() -> None:
    completion = await FakeLLMClient().complete(MESSAGES)

    assert completion.content == "Fake answer to: What is an LLM?"
    assert completion.model == "fake"
    assert completion.usage == Usage(prompt_tokens=6, completion_tokens=7, total_tokens=13)


async def test_stream_yields_the_same_answer_word_by_word_then_the_end() -> None:
    parts = [part async for part in FakeLLMClient().stream(MESSAGES)]

    words = [part for part in parts if isinstance(part, ContentDelta)]
    assert "".join(part.text for part in words) == "Fake answer to: What is an LLM?"
    assert parts[-1] == StreamEnd(
        model="fake",
        finish_reason="stop",
        usage=Usage(prompt_tokens=6, completion_tokens=7, total_tokens=13),
    )


async def test_the_question_is_the_text_of_a_message_with_parts() -> None:
    message = ChatMessage(
        role="user",
        content=[
            TextPart(text="What color"),
            ImagePart(image_url=ImageURL(url="data:image/png;base64,AAAA")),
            TextPart(text="is this?"),
        ],
    )

    completion = await FakeLLMClient().complete([message])

    assert completion.content == "Fake answer to: What color is this?"


async def test_max_tokens_cuts_the_answer_short_and_other_parameters_are_ignored() -> None:
    completion = await FakeLLMClient().complete(
        MESSAGES, parameters={"max_tokens": 2, "temperature": 0.9}
    )

    assert completion.content == "Fake answer"


async def test_without_a_user_message_the_question_is_empty() -> None:
    completion = await FakeLLMClient().complete([ChatMessage(role="system", content="Hi.")])

    assert completion.content == "Fake answer to:"


async def test_readiness_is_configurable_and_close_is_recorded() -> None:
    client = FakeLLMClient(ready=False)

    assert await client.is_ready() is False
    await client.aclose()
    assert client.closed


async def test_the_fake_takes_every_input() -> None:
    info = await FakeLLMClient().model_info()

    assert info == ModelInfo(model="fake", inputs=["text", "image", "audio", "video"])
