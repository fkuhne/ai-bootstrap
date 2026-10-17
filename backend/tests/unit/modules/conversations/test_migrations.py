"""The migrations build exactly the tables the models define.

They run on a SQLite file, as `migrate-db` runs them on PostgreSQL, where CI repeats the check.
"""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.core.config import forget_settings, settings_of
from app.modules.conversations.database.config import DatabaseSettings
from tests.unit.modules.conversations.helpers import alembic_config


@pytest.fixture
def alembic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Config:
    """Alembic's settings from pyproject.toml, on an empty SQLite file."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{(tmp_path / 'app.db').as_posix()}")
    forget_settings()
    return alembic_config()


def tables() -> set[str]:
    url = settings_of(DatabaseSettings).url.get_secret_value().replace("+aiosqlite", "")
    engine = create_engine(url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_the_migrations_build_what_the_models_define(alembic: Config) -> None:
    command.upgrade(alembic, "head")

    assert tables() == {"alembic_version", "conversations", "messages"}
    command.check(alembic)  # raises if the models hold anything the migrations don't


def test_downgrading_removes_every_table(alembic: Config) -> None:
    command.upgrade(alembic, "head")
    command.downgrade(alembic, "base")

    assert tables() == {"alembic_version"}
