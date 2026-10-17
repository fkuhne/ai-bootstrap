"""Settings of the conversations module, read from `CONVERSATIONS_*` environment variables.
Where the database is, `DATABASE_URL`, is the database's own setting."""

from pydantic_settings import SettingsConfigDict

from app.core.config import ModuleSettings


class ConversationsSettings(ModuleSettings):
    """Only the switch, `CONVERSATIONS_ENABLED`, which Compose also reads as the count of the
    migration job and of PostgreSQL."""

    model_config = SettingsConfigDict(env_prefix="CONVERSATIONS_")
