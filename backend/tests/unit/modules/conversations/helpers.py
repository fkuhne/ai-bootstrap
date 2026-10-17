"""Test doubles and settings shared by the conversations module's tests, unit and live."""

from pathlib import Path

from alembic.config import Config
from sqlalchemy import event
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.pool import ConnectionPoolEntry

from app.llm.llm_client import Usage
from app.modules.conversations.conversation_store import AnswerDetails
from app.modules.conversations.database.database import Database

# A database in memory, on SQLite, which lives as long as its engine: the unit tests' stand-in
# for PostgreSQL.
MEMORY_DATABASE_URL = "sqlite+aiosqlite://"

# A PostgreSQL that refuses connections: a closed port fails at once, inside asyncio. (SQLite on
# a missing folder fails too, but aiosqlite's worker thread may then outlive the test's loop.)
UNREACHABLE_DATABASE_URL = "postgresql+asyncpg://app:app@127.0.0.1:1/app"

BACKEND = Path(__file__).resolve().parents[4]


def alembic_config() -> Config:
    """Alembic's settings, from pyproject.toml. Its env.py reads `DATABASE_URL`."""
    config = Config(toml_file=str(BACKEND / "pyproject.toml"))
    config.attributes["configure_logging"] = False  # pytest keeps its own logging
    return config


def enforce_foreign_keys(database: Database) -> None:
    """Make SQLite check foreign keys, as PostgreSQL does: it ignores them by default, so a
    message could point to no conversation, and deleting a conversation would keep its
    messages."""

    def on_connect(connection: DBAPIConnection, _record: ConnectionPoolEntry) -> None:
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    event.listen(database.engine.sync_engine, "connect", on_connect)


# How a stored answer was made, as a conversation keeps it.
DETAILS = AnswerDetails(
    model="test-model",
    finish_reason="stop",
    usage=Usage(prompt_tokens=12, completion_tokens=8, total_tokens=20),
    first_token_ms=120.0,
    total_ms=480.5,
)
