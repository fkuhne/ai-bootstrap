"""Application-wide settings, and how every domain reads its own: once, through `settings_of`.
Each domain keeps its settings class next to its code."""

from typing import Literal, cast

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]


class AppSettings(BaseSettings):
    """Settings shared by the whole application, read from `APP_*` environment variables."""

    # extra: the environment holds other domains' settings too.
    # env_ignore_empty: a variable set to "" in .env means "use the default".
    model_config = SettingsConfigDict(env_prefix="APP_", extra="ignore", env_ignore_empty=True)

    name: str = "ai-bootstrap"
    log_level: LogLevel = "INFO"
    docs_enabled: bool = True

    @field_validator("log_level", mode="before")
    @classmethod
    def _upper_case(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value


class ModuleSettings(BaseSettings):
    """What every module's settings class derives from, giving its own prefix, such as `RAG_`
    (docs/foundations.md#modules). `enabled`, read as `<NAME>_ENABLED`, is the module's switch:
    0 turns it off, its endpoints, its readiness check and, read by Compose, its own services.
    Written 0 or 1, as Compose reads it as their count."""

    # extra: the environment holds other domains' settings too.
    # env_ignore_empty: a variable set to "" in .env means "use the default".
    model_config = SettingsConfigDict(extra="ignore", env_ignore_empty=True)

    enabled: bool = True


# The settings read so far, by class.
_read: dict[type[BaseSettings], BaseSettings] = {}


def settings_of[S: BaseSettings](cls: type[S]) -> S:
    """A settings class, read from the environment once, then kept: every domain reads its
    settings so, the core's included."""
    if cls not in _read:
        _read[cls] = cls()
    return cast(S, _read[cls])


def forget_settings() -> None:
    """Forget every class read, so the next read sees the environment as it is now, as each
    test does to start from the defaults."""
    _read.clear()
