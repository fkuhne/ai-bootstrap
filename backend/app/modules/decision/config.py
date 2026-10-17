"""Settings of the decision module, read from `DECISION_*` environment variables."""

from typing import Literal

from pydantic import Field, HttpUrl, SecretStr
from pydantic_settings import SettingsConfigDict

from app.core.config import ModuleSettings

Provider = Literal["systemone", "fake"]


class DecisionSettings(ModuleSettings):
    """How to reach the decision model: any System One endpoint, or the fake. The switch,
    `DECISION_ENABLED`, also turns the local `decision` service off."""

    model_config = SettingsConfigDict(env_prefix="DECISION_")

    provider: Provider = "systemone"
    # The endpoint's base: llama.cpp's server, https://api.typesafe.ai/v1, or
    # https://openrouter.ai/api/v1. The client adds /systemone.
    base_url: HttpUrl = HttpUrl("http://decision:8080/v1")
    # llama.cpp's server needs no key.
    api_key: SecretStr = SecretStr("local")
    # llama.cpp's server answers with the model it loaded, whatever the name; TypeSafe and
    # OpenRouter need theirs, such as jev-latest or typesafe/jev-1.13.
    model: str = "local"
    timeout_seconds: float = Field(default=60, gt=0)
