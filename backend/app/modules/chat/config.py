"""Settings of the chat module, read from `CHAT_*` environment variables."""

from pydantic_settings import SettingsConfigDict

from app.core.config import ModuleSettings


class ChatSettings(ModuleSettings):
    """Only the switch, `CHAT_ENABLED`: chat has nothing else to set."""

    model_config = SettingsConfigDict(env_prefix="CHAT_")
