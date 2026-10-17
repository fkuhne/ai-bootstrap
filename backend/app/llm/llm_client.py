"""The LLM port: what the rest of the backend needs from a chat model.

Messages carry text, or parts that may hold images, audio and video, in the shape of
OpenAI's Chat Completions API. Any generation parameter passes through as given; the
provider decides which it accepts (docs/foundations.md#the-llm-port).
"""

from collections.abc import AsyncGenerator, Mapping, Sequence
from typing import Annotated, Literal, Protocol, Self

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, JsonValue, model_validator

Role = Literal["system", "user", "assistant"]

# What a message to the model may carry, besides text, when the model takes it.
Input = Literal["text", "image", "audio", "video"]
INPUTS: tuple[Input, ...] = ("text", "image", "audio", "video")


def known_inputs(names: Sequence[str]) -> list[Input]:
    """The inputs among `names`, in `INPUTS`' order, text always first; other names, such as
    a server's `file`, are left out."""
    given = set(names) | {"text"}
    return [name for name in INPUTS if name in given]


# Generation parameters, such as temperature, seed or reasoning_effort, sent as given.
Parameters = Mapping[str, JsonValue]

# Parameters the client sets itself, which a caller can't override.
RESERVED_PARAMETERS = frozenset({"model", "messages", "stream", "stream_options"})


def _not_reserved(parameters: dict[str, JsonValue]) -> dict[str, JsonValue]:
    if reserved := sorted(RESERVED_PARAMETERS & parameters.keys()):
        raise ValueError(f"the backend sets these itself: {', '.join(reserved)}")
    return parameters


# Generation parameters as a request carries them, for every endpoint that calls the model.
RequestParameters = Annotated[
    dict[str, JsonValue],
    AfterValidator(_not_reserved),
    Field(
        description="Any generation parameter the model accepts, such as temperature, seed or "
        "reasoning_effort, sent as given. The provider's defaults apply to the rest."
    ),
]


class _Part(BaseModel):
    model_config = ConfigDict(frozen=True)


class TextPart(_Part):
    type: Literal["text"] = "text"
    text: str = Field(min_length=1)


class ImageURL(_Part):
    url: str = Field(min_length=1, description="An http(s) URL, or a `data:` URI with base64.")
    detail: Literal["auto", "low", "high"] | None = None


class ImagePart(_Part):
    type: Literal["image_url"] = "image_url"
    image_url: ImageURL


class Media(_Part):
    """Audio or video, as base64 `data` or a `url`; exactly one of the two."""

    data: str | None = Field(default=None, min_length=1)
    url: str | None = Field(default=None, min_length=1)
    format: str | None = Field(default=None, description="Such as wav or mp3, for audio.")

    @model_validator(mode="after")
    def _one_source(self) -> Self:
        if (self.data is None) == (self.url is None):
            raise ValueError("give either data or url")
        return self


class AudioPart(_Part):
    type: Literal["input_audio"] = "input_audio"
    input_audio: Media


class VideoPart(_Part):
    type: Literal["input_video"] = "input_video"
    input_video: Media


ContentPart = Annotated[TextPart | ImagePart | AudioPart | VideoPart, Field(discriminator="type")]

# What a message says: text, or a list of parts. Neither may be empty.
Content = Annotated[str, Field(min_length=1)] | Annotated[list[ContentPart], Field(min_length=1)]


def text_of(content: str | Sequence[ContentPart]) -> str:
    """A message's text: its content, or its text parts joined, without its media."""
    if isinstance(content, str):
        return content
    return " ".join(part.text for part in content if isinstance(part, TextPart))


class ChatMessage(BaseModel):
    """One message of the conversation sent to the model."""

    model_config = ConfigDict(frozen=True)

    role: Role
    content: Content


class Usage(BaseModel):
    """Tokens one completion consumed, as the server reports them."""

    model_config = ConfigDict(frozen=True)

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class Completion(BaseModel):
    """A whole answer from the model, with its reasoning when the model shows it."""

    model_config = ConfigDict(frozen=True)

    content: str
    reasoning: str | None = None
    model: str
    finish_reason: str | None = None
    usage: Usage | None = None


class ContentDelta(BaseModel):
    """The next piece of the answer."""

    model_config = ConfigDict(frozen=True)

    text: str


class ReasoningDelta(BaseModel):
    """The next piece of the model's reasoning, which comes before the answer."""

    model_config = ConfigDict(frozen=True)

    text: str


class StreamEnd(BaseModel):
    """The last part of a stream that ended normally."""

    model_config = ConfigDict(frozen=True)

    model: str
    finish_reason: str | None = None
    usage: Usage | None = None


StreamPart = ContentDelta | ReasoningDelta | StreamEnd


class ModelInfo(BaseModel):
    """The model that answers, and what a message to it may carry."""

    model_config = ConfigDict(frozen=True)

    model: str = Field(description="The model's name, as its server lists it.")
    inputs: list[Input] = Field(
        description="Text, and images, audio or video when the model takes them, as its "
        "server reports them, or as `LLM_INPUTS` says."
    )


class LLMClient(Protocol):
    """A chat model the backend can call. Implementations are interchangeable (Strategy).

    Every method raises the core's `ServiceError`s on failure (`app.core.errors`), never SDK
    errors.
    """

    async def complete(
        self, messages: Sequence[ChatMessage], *, parameters: Parameters | None = None
    ) -> Completion:
        """Return the whole answer to `messages`."""
        ...

    def stream(
        self, messages: Sequence[ChatMessage], *, parameters: Parameters | None = None
    ) -> AsyncGenerator[StreamPart]:
        """Yield the reasoning and the answer to `messages` piece by piece, as the model
        produces them, then a `StreamEnd`. Closing the generator early stops the model."""
        ...

    async def is_ready(self) -> bool:
        """Tell whether the model can take requests right now."""
        ...

    async def model_info(self) -> ModelInfo:
        """Tell which model answers, and the inputs it accepts."""
        ...

    async def aclose(self) -> None:
        """Release connections and other resources."""
        ...
