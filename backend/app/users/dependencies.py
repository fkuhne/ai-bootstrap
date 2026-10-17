"""The current user, as one FastAPI dependency every domain uses."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header


async def current_user(
    x_user_id: Annotated[
        UUID,
        Header(
            description="The anonymous id the browser generated and keeps: a UUID. What a user "
            "stores belongs to it, and another id sees none of it.",
            examples=["3f2b8c1e-6d4a-4f7e-9b0a-2c5d8e1f4a7b"],
        ),
    ],
) -> UUID:
    """Whose data a request reads or writes. There is no login yet: the browser makes a random
    UUID once, keeps it, and sends it as `X-User-Id`. A missing or malformed one is refused
    with 422 before the endpoint runs. Replace this function to add real authentication."""
    return x_user_id


CurrentUserDep = Annotated[UUID, Depends(current_user)]
