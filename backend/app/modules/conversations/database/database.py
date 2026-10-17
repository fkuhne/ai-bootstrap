"""The database, reached through SQLAlchemy's async engine."""

import asyncio

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.core.services import READINESS_TIMEOUT_SECONDS
from app.modules.conversations.database.config import DatabaseSettings


class Database:
    """A pool of connections to the database, and the sessions that borrow them.

    Each operation opens a short session from `sessions`, and its connection goes back to the
    pool when the session ends. So no connection waits idle while the model answers, and a
    few connections serve many requests at once. Nothing connects until the first use.

    Tests pass an in-memory SQLite engine. It keeps a single connection, so every session
    sees the same tables.
    """

    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine
        # Without expiring on commit, a stored row's fields stay readable after its session.
        self.sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def connect(cls, settings: DatabaseSettings) -> Database:
        """A database on the URL the settings name.

        Each connection is checked before the pool lends it, so a restarted database costs a
        reconnection rather than a failed request.
        """
        return cls(create_async_engine(settings.url.get_secret_value(), pool_pre_ping=True))

    @property
    def location(self) -> str:
        """The database's URL with its password hidden, for logs."""
        return self.engine.url.render_as_string(hide_password=True)

    async def is_ready(self) -> bool:
        """Tell whether the database answers a query right now. A host that never answers would
        otherwise hold the check for asyncpg's own connection timeout, 60 s."""
        try:
            async with asyncio.timeout(READINESS_TIMEOUT_SECONDS), self.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        # A refused connection or an unknown host raises OSError, not wrapped by SQLAlchemy.
        # TimeoutError is an OSError too.
        except SQLAlchemyError, OSError:
            return False
        return True

    async def aclose(self) -> None:
        """Close the pool's connections."""
        await self.engine.dispose()
