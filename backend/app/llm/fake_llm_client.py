"""A deterministic LLM client, for tests and for running the backend without a model."""

from collections.abc import AsyncGenerator, Sequence

from app.llm.llm_client import (
    INPUTS,
    ChatMessage,
    Completion,
    ContentDelta,
    LLMClient,
    ModelInfo,
    Parameters,
    StreamEnd,
    StreamPart,
    Usage,
    text_of,
)


class FakeLLMClient(LLMClient):
    """Answers "Fake answer to: <last user message's text>" without calling any model.

    `LLM_PROVIDER=fake` selects it. It honours `max_tokens`, counted in words, and ignores
    every other parameter. It takes every input, and ignores all but text, so an app's
    attachments can be tried without a model.
    """

    model = "fake"

    def __init__(self, *, ready: bool = True) -> None:
        self._ready = ready
        self.closed = False

    async def complete(
        self, messages: Sequence[ChatMessage], *, parameters: Parameters | None = None
    ) -> Completion:
        words = _answer_words(messages, parameters)
        return Completion(
            content=" ".join(words),
            model=self.model,
            finish_reason="stop",
            usage=_usage(messages, words),
        )

    async def stream(
        self, messages: Sequence[ChatMessage], *, parameters: Parameters | None = None
    ) -> AsyncGenerator[StreamPart]:
        words = _answer_words(messages, parameters)
        for index, word in enumerate(words):
            yield ContentDelta(text=word if index == 0 else f" {word}")
        yield StreamEnd(model=self.model, finish_reason="stop", usage=_usage(messages, words))

    async def is_ready(self) -> bool:
        return self._ready

    async def model_info(self) -> ModelInfo:
        return ModelInfo(model=self.model, inputs=list(INPUTS))

    async def aclose(self) -> None:
        self.closed = True


def _answer_words(messages: Sequence[ChatMessage], parameters: Parameters | None) -> list[str]:
    question = next((text_of(m.content) for m in reversed(messages) if m.role == "user"), "")
    words = f"Fake answer to: {question}".split()
    limit = (parameters or {}).get("max_tokens")
    return words[:limit] if isinstance(limit, int) and limit > 0 else words


def _usage(messages: Sequence[ChatMessage], words: list[str]) -> Usage:
    prompt_tokens = sum(len(text_of(message.content).split()) for message in messages)
    return Usage(
        prompt_tokens=prompt_tokens,
        completion_tokens=len(words),
        total_tokens=prompt_tokens + len(words),
    )
