"""The database against the real PostgreSQL, after migrate-db. Run with the stack up:

docker compose run --rm backend-checks pytest -m integration --no-cov
"""

from collections.abc import AsyncIterator

import pytest
from alembic.script import ScriptDirectory
from sqlalchemy import text

from app.core.config import settings_of
from app.modules.conversations.database.config import DatabaseSettings
from app.modules.conversations.database.database import Database
from tests.unit.modules.conversations.helpers import alembic_config

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


@pytest.fixture
async def live_database() -> AsyncIterator[Database]:
    database = Database.connect(settings_of(DatabaseSettings))
    yield database
    await database.aclose()


async def test_the_postgres_service_is_ready(live_database: Database) -> None:
    assert await live_database.is_ready()


async def test_it_runs_the_pinned_release(live_database: Database) -> None:
    async with live_database.sessions() as session:
        version = await session.scalar(text("SHOW server_version"))

    assert version == "18.6"


async def test_migrate_db_brought_it_to_the_latest_migration(live_database: Database) -> None:
    head = ScriptDirectory.from_config(alembic_config()).get_current_head()
    async with live_database.sessions() as session:
        exists = await session.scalar(text("SELECT to_regclass('alembic_version') IS NOT NULL"))
        applied = (
            await session.scalar(text("SELECT version_num FROM alembic_version"))
            if exists
            else None
        )

    assert applied == head  # None for both while there are no migrations
