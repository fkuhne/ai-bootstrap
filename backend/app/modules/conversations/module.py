"""The conversations module, as the core plugs it in (docs/foundations.md#conversations)."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.core.config import settings_of
from app.core.modules import Module
from app.modules.conversations.config import ConversationsSettings
from app.modules.conversations.database.config import DatabaseSettings
from app.modules.conversations.database.database import Database
from app.modules.conversations.database.dependencies import get_database
from app.modules.conversations.router import router
from app.modules.conversations.schemas import ConversationDoneEvent
from app.modules.conversations.sql_conversation_store import SqlConversationStore

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Connect to the database when the app starts, and close it when it stops."""
    database = Database.connect(settings_of(DatabaseSettings))
    logger.info("Conversations in the database at %s.", database.location)
    app.state.database = database
    app.state.conversation_store = SqlConversationStore(database.sessions)
    try:
        yield
    finally:
        await database.aclose()


async def is_ready(request: Request) -> bool:
    database = await get_database(request)
    return await database.is_ready()


MODULE = Module(
    name="conversations",
    router=router,
    settings=ConversationsSettings,
    more_settings=(DatabaseSettings,),
    lifespan=lifespan,
    is_ready=is_ready,
    event_models=(ConversationDoneEvent,),
)
