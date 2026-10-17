"""FastAPI dependencies of the database domain."""

from typing import Annotated, cast

from fastapi import Depends, Request

from app.modules.conversations.database.database import Database


async def get_database(request: Request) -> Database:
    """The database the lifespan created for this application. Tests override this."""
    return cast(Database, request.app.state.database)


DatabaseDep = Annotated[Database, Depends(get_database)]
