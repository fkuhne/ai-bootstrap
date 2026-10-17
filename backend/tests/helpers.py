"""Types, parsers and test doubles shared by the tests and their fixtures."""

import json
from collections.abc import AsyncGenerator, Callable, Sequence
from typing import Any

from pydantic_settings import SettingsConfigDict

from app.core.config import ModuleSettings
from app.core.errors import ServiceError
from app.llm.llm_client import (
    ChatMessage,
    Completion,
    ContentDelta,
    LLMClient,
    ModelInfo,
    Parameters,
    ReasoningDelta,
    StreamEnd,
    StreamPart,
    Usage,
)

UseLLM = Callable[[LLMClient], None]


class ExampleSettings(ModuleSettings):
    """The settings of a module the tests make, on by default."""

    model_config = SettingsConfigDict(env_prefix="EXAMPLE_")


class OffSettings(ModuleSettings):
    """The settings of a module the tests make, off by default."""

    model_config = SettingsConfigDict(env_prefix="OFF_")

    enabled: bool = False


def events(body: str) -> list[tuple[str, dict[str, Any]]]:
    """Parse a server-sent-events body into (event, data) pairs, skipping comments."""
    parsed = []
    for block in body.strip().split("\n\n"):
        lines = [line for line in block.splitlines() if not line.startswith(":")]
        fields = dict(line.split(": ", 1) for line in lines)
        if "data" in fields:
            parsed.append((fields.get("event", "message"), json.loads(fields["data"])))
    return parsed


USAGE = {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5}


class ScriptedLLM(LLMClient):
    """Reasons, answers in two pieces, and records what it was sent; or fails with `error`
    after `pieces_first` stream parts."""

    def __init__(self, error: ServiceError | None = None, *, pieces_first: int = 0) -> None:
        self.error = error
        self.pieces_first = pieces_first
        self.sent: list[tuple[Sequence[ChatMessage], Parameters | None]] = []

    async def complete(
        self, messages: Sequence[ChatMessage], *, parameters: Parameters | None = None
    ) -> Completion:
        self.sent.append((messages, parameters))
        if self.error:
            raise self.error
        return Completion(content="Hello", reasoning="Greet.", model="scripted")

    async def stream(
        self, messages: Sequence[ChatMessage], *, parameters: Parameters | None = None
    ) -> AsyncGenerator[StreamPart]:
        self.sent.append((messages, parameters))
        parts: list[StreamPart] = [
            ReasoningDelta(text="Greet."),
            ContentDelta(text="Hel"),
            ContentDelta(text="lo"),
            StreamEnd(model="scripted", finish_reason="stop", usage=Usage(**USAGE)),
        ]
        if self.error:
            parts = parts[: self.pieces_first]
        for part in parts:
            yield part
        if self.error:
            raise self.error

    async def is_ready(self) -> bool:
        return True

    async def model_info(self) -> ModelInfo:
        if self.error:
            raise self.error
        return ModelInfo(model="scripted", inputs=["text"])

    async def aclose(self) -> None:
        return None
