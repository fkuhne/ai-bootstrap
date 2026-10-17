"""Adapter from the LLM port to any OpenAI-compatible Chat Completions API."""

import asyncio
import logging
from collections.abc import AsyncGenerator, Awaitable, Callable, Sequence
from typing import Any, cast

import openai
from openai import AsyncOpenAI
from openai.types import CompletionUsage
from openai.types.chat import ChatCompletionMessageParam

from app.core.services import READINESS_TIMEOUT_SECONDS
from app.llm.llm_client import (
    ChatMessage,
    Completion,
    ContentDelta,
    Input,
    LLMClient,
    ModelInfo,
    Parameters,
    ReasoningDelta,
    StreamEnd,
    StreamPart,
    Usage,
    known_inputs,
)
from app.llm.openai_errors import translate

logger = logging.getLogger(__name__)

# How the endpoint is named in errors.
SERVICE = "The LLM endpoint"

# Failures worth another try: the request never reached the model (a connection error), the
# server asked to slow down (429), or it failed (5xx). A timeout is not among them, although
# the SDK counts it as a connection error: the model may still be working, and a retry would
# start the same generation again, multiplying the wait. The SDK's own retries are off, since
# it retries timeouts too.
RETRYABLE = (openai.APIConnectionError, openai.RateLimitError, openai.InternalServerError)

# The wait before the first retry, doubled before each next one.
RETRY_DELAY_SECONDS = 0.5

# Where servers put the model's reasoning: llama.cpp and DeepSeek use the first, Ollama and
# OpenRouter the second.
REASONING_FIELDS = ("reasoning_content", "reasoning")


class OpenAICompatibleClient(LLMClient):
    """Talks to llama.cpp's server, Ollama Cloud, OpenAI, Anthropic's compatibility layer, or
    any other OpenAI-compatible API (Adapter).

    It sends the caller's parameters as given and adds none of its own, so each provider's
    defaults apply.
    """

    def __init__(
        self,
        client: AsyncOpenAI,
        *,
        model: str,
        inputs: Sequence[Input] | None = None,
        max_retries: int = 0,
        retry_delay_seconds: float = RETRY_DELAY_SECONDS,
    ) -> None:
        self._client = client
        self._model = model
        self._inputs = None if inputs is None else known_inputs(inputs)
        self._max_retries = max_retries
        self._retry_delay = retry_delay_seconds

    async def complete(
        self, messages: Sequence[ChatMessage], *, parameters: Parameters | None = None
    ) -> Completion:
        try:
            response = await self._retrying(
                lambda: self._client.chat.completions.create(
                    model=self._model,
                    messages=_to_openai(messages),
                    extra_body=dict(parameters or {}),
                )
            )
        except openai.APIError as error:
            raise translate(error, SERVICE) from error
        choice = response.choices[0]
        return Completion(
            content=choice.message.content or "",
            reasoning=_reasoning(choice.message.model_extra) or None,
            model=response.model,
            finish_reason=choice.finish_reason,
            usage=_usage(response.usage),
        )

    async def stream(
        self, messages: Sequence[ChatMessage], *, parameters: Parameters | None = None
    ) -> AsyncGenerator[StreamPart]:
        # Retried until the stream opens; a failure once pieces have come ends it.
        try:
            chunks = await self._retrying(
                lambda: self._client.chat.completions.create(
                    model=self._model,
                    messages=_to_openai(messages),
                    stream=True,
                    # The usage comes in a last chunk without choices.
                    stream_options={"include_usage": True},
                    extra_body=dict(parameters or {}),
                )
            )
        except openai.APIError as error:
            raise translate(error, SERVICE) from error
        model, finish_reason, usage = self._model, None, None
        try:
            async for chunk in chunks:
                model = chunk.model or model
                usage = _usage(chunk.usage) or usage
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                finish_reason = choice.finish_reason or finish_reason
                if reasoning := _reasoning(choice.delta.model_extra):
                    yield ReasoningDelta(text=reasoning)
                if choice.delta.content:
                    yield ContentDelta(text=choice.delta.content)
        except openai.APIError as error:
            raise translate(error, SERVICE) from error
        finally:
            # Closing the response is how a reader that stops early stops the server's generation.
            await chunks.close()
        yield StreamEnd(model=model, finish_reason=finish_reason, usage=usage)

    async def is_ready(self) -> bool:
        """Try a minimal completion instead of listing models.

        A server can list its model before it can serve it: after a restart, llama.cpp's
        server answered `/v1/models` before its own `/health` did, so a client trusting the
        list saw ready while a real call still got a 503. The short, dedicated timeout keeps
        this from queuing behind a real request on a single-slot server.

        A 400 counts as ready: the endpoint and the model answered, and refused only the
        probe's own `max_tokens`, as some providers' newer models do.
        """
        try:
            await self._client.chat.completions.create(
                model=self._model,
                messages=_to_openai([ChatMessage(role="user", content="ping")]),
                max_tokens=1,
                timeout=READINESS_TIMEOUT_SECONDS,
            )
        except openai.BadRequestError:
            return True
        except openai.APIError:
            return False
        return True

    async def model_info(self) -> ModelInfo:
        """The configured model, as the server lists it: under its name, or the only one
        listed, as llama.cpp lists the one it loaded under its own name.

        llama.cpp reports the inputs under `architecture.input_modalities`, as OpenRouter
        does. A model that reports none takes text alone, unless the settings' inputs say
        otherwise; with those, the server isn't asked.
        """
        if self._inputs is not None:
            return ModelInfo(model=self._model, inputs=self._inputs)
        try:
            page = await self._retrying(self._client.models.list)
        except openai.APIError as error:
            raise translate(error, SERVICE) from error
        named = [model for model in page.data if model.id == self._model]
        found = named[0] if named else page.data[0] if len(page.data) == 1 else None
        if found is None:
            return ModelInfo(model=self._model, inputs=["text"])
        extra = found.model_extra or {}
        architecture = extra.get("architecture") or {}
        reported = architecture.get("input_modalities") or extra.get("input_modalities") or []
        return ModelInfo(model=found.id, inputs=known_inputs([str(name) for name in reported]))

    async def aclose(self) -> None:
        await self._client.close()

    async def _retrying[T](self, call: Callable[[], Awaitable[T]]) -> T:
        """Make the call, and again after a failure in `RETRYABLE`, up to `max_retries` more
        times, waiting a little longer before each."""
        retry = 0
        while True:
            try:
                return await call()
            except openai.APITimeoutError:
                raise
            except RETRYABLE as error:
                if retry == self._max_retries:
                    raise
                retry += 1
                delay = self._retry_delay * 2 ** (retry - 1)
                logger.warning(
                    "The LLM endpoint failed (%s); retrying in %.1f s (retry %d of %d).",
                    type(error).__name__,
                    delay,
                    retry,
                    self._max_retries,
                )
                await asyncio.sleep(delay)


def _to_openai(messages: Sequence[ChatMessage]) -> list[ChatCompletionMessageParam]:
    # The port's messages have the API's shape already; only the unset fields go.
    return [
        cast(ChatCompletionMessageParam, message.model_dump(exclude_none=True))
        for message in messages
    ]


def _reasoning(extra: dict[str, Any] | None) -> str:
    """The reasoning a message or a delta carries, under whichever name the server uses."""
    for field in REASONING_FIELDS:
        value = (extra or {}).get(field)
        if isinstance(value, str) and value:
            return value
    return ""


def _usage(usage: CompletionUsage | None) -> Usage | None:
    if usage is None:
        return None
    return Usage(
        prompt_tokens=usage.prompt_tokens,
        completion_tokens=usage.completion_tokens,
        total_tokens=usage.total_tokens,
    )
