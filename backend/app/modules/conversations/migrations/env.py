"""Alembic's entry point: applies the migrations in `versions/` to the database.

The database is the one `DATABASE_URL` names, read through the module's settings, and the
logs use the backend's format. `alembic upgrade head --sql` prints the SQL instead of running
it. A domain's tables join `Base.metadata` when its models module is imported here.
"""

import asyncio
from typing import Any, Literal

from alembic import context
from alembic.autogenerate.api import AutogenContext
from sqlalchemy.engine import Connection

from app.core.config import AppSettings, settings_of
from app.core.logging import configure_logging
from app.modules.conversations import models  # noqa: F401  (registers the tables on Base.metadata)
from app.modules.conversations.database.base import Base, UtcDateTime
from app.modules.conversations.database.config import DatabaseSettings
from app.modules.conversations.database.database import Database

config = context.config
# Tests that run the migrations keep their own logging.
if config.attributes.get("configure_logging", True):
    configure_logging(settings_of(AppSettings).log_level)


def render_item(
    type_: str,
    item: Any,
    autogen_context: AutogenContext,  # noqa: ARG001  (Alembic's signature)
) -> str | Literal[False]:
    """Write the app's own column types as the standard types they store.

    A migration then never imports the app's code, which may change after it was written.
    """
    if type_ == "type" and isinstance(item, UtcDateTime):
        return "sa.DateTime(timezone=True)"
    return False


# For every run. Batch mode writes column changes so that SQLite, which can't alter most of a
# table in place, applies them too: the unit tests run the migrations on it.
OPTIONS: dict[str, Any] = {
    "target_metadata": Base.metadata,
    "render_item": render_item,
    "render_as_batch": True,
}


def run_migrations_offline() -> None:
    """Write the migrations' SQL to the output, without a database."""
    context.configure(
        url=settings_of(DatabaseSettings).url.get_secret_value(),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        **OPTIONS,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, **OPTIONS)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Apply the migrations through the same engine the backend uses."""
    database = Database.connect(settings_of(DatabaseSettings))
    try:
        async with database.engine.connect() as connection:
            await connection.run_sync(run_migrations)
    finally:
        await database.aclose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
