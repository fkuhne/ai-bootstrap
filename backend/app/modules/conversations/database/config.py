"""Settings of the database domain, read from `DATABASE_*` environment variables."""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Where the database is.

    The default URL suits code running on the host, against the port the `postgres` service
    publishes. Docker Compose points it at the service instead.
    """

    model_config = SettingsConfigDict(env_prefix="DATABASE_", extra="ignore", env_ignore_empty=True)

    # A SQLAlchemy URL. It holds the password, so it's kept out of logs and error messages.
    url: SecretStr = SecretStr("postgresql+asyncpg://app:app-local@localhost:5433/app")
