"""The conversations module's tests run against an app with the module in it, and a database in
memory."""

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from app.main import create_app
from app.modules.conversations import (
    MODULE,
    models,  # noqa: F401  (registers the tables on Base.metadata)
)
from app.modules.conversations.database.base import Base
from app.modules.conversations.database.config import DatabaseSettings
from app.modules.conversations.database.database import Database
from app.modules.conversations.database.dependencies import get_database
from tests.unit.modules.conversations.helpers import MEMORY_DATABASE_URL, enforce_foreign_keys


@pytest.fixture
def app() -> FastAPI:
    """The core and the conversations module, in place of the core alone."""
    return create_app(modules=[MODULE])


@pytest.fixture
async def database() -> AsyncIterator[Database]:
    """A database in memory, on SQLite, with the app's tables, built from the models, and
    foreign keys enforced as on PostgreSQL. Every session sees the same tables; a migration
    test checks that the migrations build the same."""
    database = Database.connect(DatabaseSettings(url=SecretStr(MEMORY_DATABASE_URL)))
    enforce_foreign_keys(database)
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield database
    await database.aclose()


@pytest.fixture
def use_database(app: FastAPI, database: Database) -> Database:
    """Make the app's routes use the in-memory database, as the lifespan would."""
    app.dependency_overrides[get_database] = lambda: database
    return database
