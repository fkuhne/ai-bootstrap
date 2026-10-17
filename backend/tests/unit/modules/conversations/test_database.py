import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta, timezone
from typing import cast

import pytest
from fastapi import FastAPI
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.dialects import sqlite
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.requests import Request

from app.core.config import settings_of
from app.modules.conversations.database import database as database_module
from app.modules.conversations.database.base import UtcDateTime
from app.modules.conversations.database.config import DatabaseSettings
from app.modules.conversations.database.database import Database
from app.modules.conversations.database.dependencies import get_database
from tests.unit.modules.conversations.helpers import UNREACHABLE_DATABASE_URL

pytestmark = pytest.mark.anyio


def test_the_default_url_is_the_host_port_of_the_postgres_service() -> None:
    url = settings_of(DatabaseSettings).url.get_secret_value()

    assert url == "postgresql+asyncpg://app:app-local@localhost:5433/app"


def test_the_password_stays_out_of_the_settings_and_the_logs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://app:s3cret@postgres:5432/app")

    settings = settings_of(DatabaseSettings)
    database = Database.connect(settings)  # creates the pool, but connects to nothing

    assert "s3cret" not in repr(settings)
    assert database.location == "postgresql+asyncpg://app:***@postgres:5432/app"


async def test_sessions_share_one_database(database: Database) -> None:
    async with database.sessions.begin() as session:
        await session.execute(text("CREATE TABLE notes (body TEXT)"))
        await session.execute(text("INSERT INTO notes VALUES ('kept')"))

    async with database.sessions() as session:
        stored = await session.scalar(text("SELECT body FROM notes"))

    assert stored == "kept"


async def test_a_database_that_answers_is_ready(database: Database) -> None:
    assert await database.is_ready()


async def test_a_database_that_cant_be_opened_isnt_ready() -> None:
    database = Database.connect(DatabaseSettings(url=SecretStr(UNREACHABLE_DATABASE_URL)))

    assert not await database.is_ready()
    await database.aclose()


class SlowEngine:
    """An engine whose connections take a second to open."""

    @asynccontextmanager
    async def connect(self) -> AsyncIterator[None]:
        await asyncio.sleep(1)
        yield


async def test_a_database_that_answers_too_late_isnt_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(database_module, "READINESS_TIMEOUT_SECONDS", 0.01)

    assert not await Database(cast(AsyncEngine, SlowEngine())).is_ready()


async def test_the_dependency_returns_the_database_the_lifespan_created(
    database: Database,
) -> None:
    app = FastAPI()
    app.state.database = database

    assert await get_database(Request({"type": "http", "app": app})) is database


SQLITE = sqlite.dialect()


def test_a_time_is_stored_in_utc() -> None:
    sao_paulo = timezone(timedelta(hours=-3))
    noon = datetime(2026, 10, 3, 12, 0, tzinfo=sao_paulo)

    stored = UtcDateTime().process_bind_param(noon, SQLITE)

    assert stored == noon
    assert stored is not None
    assert stored.tzinfo == UTC


def test_a_time_without_its_zone_is_refused() -> None:
    with pytest.raises(ValueError, match="needs its time zone"):
        UtcDateTime().process_bind_param(datetime(2026, 10, 3, 12, 0), SQLITE)


def test_a_time_read_without_its_zone_is_utc() -> None:
    column = UtcDateTime()

    read = column.process_result_value(datetime(2026, 10, 3, 15, 0), SQLITE)

    assert read == datetime(2026, 10, 3, 15, 0, tzinfo=UTC)
    assert column.process_result_value(None, SQLITE) is None
    assert column.process_bind_param(None, SQLITE) is None
