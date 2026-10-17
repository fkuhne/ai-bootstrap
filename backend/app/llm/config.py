"""Settings of the LLM domain, read from `LLM_*` environment variables."""

from typing import Annotated, Literal

from pydantic import Field, HttpUrl, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from app.llm.llm_client import Input, known_inputs

Provider = Literal["openai-compatible", "fake"]


class LLMSettings(BaseSettings):
    """How to reach the chat model: any OpenAI-compatible API, or the fake.

    The defaults reach the local llama.cpp server from inside Docker Compose. A cloud model
    is a different URL, key and model name, nothing more.
    """

    model_config = SettingsConfigDict(env_prefix="LLM_", extra="ignore", env_ignore_empty=True)

    provider: Provider = "openai-compatible"
    base_url: HttpUrl = HttpUrl("http://llm:8080/v1")
    # llama.cpp needs no key; the SDK needs a value all the same.
    api_key: SecretStr = SecretStr("local")
    # llama.cpp serves the one model it loaded, whatever the name.
    model: str = "local"
    timeout_seconds: float = Field(default=300, gt=0)
    max_retries: int = Field(default=2, ge=0)
    # The model's inputs, such as "text,image", for a provider that doesn't report them;
    # unset, the server's model list says.
    inputs: Annotated[list[Input], NoDecode] | None = None

    @field_validator("inputs", mode="before")
    @classmethod
    def _comma_separated(cls, value: object) -> object:
        if isinstance(value, str):
            names = [name.strip().lower() for name in value.split(",") if name.strip()]
            if unknown := sorted(set(names) - {*known_inputs(names)}):
                raise ValueError(f"unknown inputs: {', '.join(unknown)}")
            return known_inputs(names)
        return value
