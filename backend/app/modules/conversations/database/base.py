"""The base of every table, and the column types they share."""

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Dialect, MetaData, TypeDecorator
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase

# How constraints and indexes are named, so a migration names them the same way on every
# database, and a later migration can find them by name.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """The base of every table. Its metadata is what Alembic compares migrations with."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


# JSON, kept as jsonb on PostgreSQL: parsed once when written, as PostgreSQL's documentation
# recommends for most uses. Plain JSON on SQLite.
JsonDocument = JSON().with_variant(JSONB(), "postgresql")


def utc_now() -> datetime:
    """The current time in UTC, with its zone."""
    return datetime.now(UTC)


class UtcDateTime(TypeDecorator[datetime]):
    """A point in time, stored in UTC and always read back with its zone.

    PostgreSQL keeps the zone; SQLite, which the unit tests use, drops it. A time without a
    zone is refused, since nothing could tell which zone it meant.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    # The signatures are SQLAlchemy's, which passes the dialect.
    def process_bind_param(
        self,
        value: datetime | None,
        dialect: Dialect,  # noqa: ARG002
    ) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError(f"A time to store needs its time zone: {value!r}.")
        return value.astimezone(UTC)

    def process_result_value(
        self,
        value: datetime | None,
        dialect: Dialect,  # noqa: ARG002
    ) -> datetime | None:
        if value is None or value.tzinfo is not None:
            return value
        return value.replace(tzinfo=UTC)
