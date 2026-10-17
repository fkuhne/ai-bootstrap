from uuid import uuid4

import httpx2
import pytest
from fastapi import FastAPI

from app.users.dependencies import CurrentUserDep

pytestmark = pytest.mark.anyio


@pytest.fixture
def whoami() -> FastAPI:
    app = FastAPI()

    @app.get("/whoami")
    async def whoami(user_id: CurrentUserDep) -> str:
        return str(user_id)

    return app


async def get(app: FastAPI, headers: dict[str, str]) -> httpx2.Response:
    transport = httpx2.ASGITransport(app=app)
    async with httpx2.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get("/whoami", headers=headers)


async def test_the_current_user_is_the_id_the_browser_sends(whoami: FastAPI) -> None:
    user = str(uuid4())

    response = await get(whoami, {"X-User-Id": user})

    assert response.json() == user


@pytest.mark.parametrize("headers", [{}, {"X-User-Id": "alice"}])
async def test_a_request_needs_a_uuid_user_id(whoami: FastAPI, headers: dict[str, str]) -> None:
    response = await get(whoami, headers)

    assert response.status_code == httpx2.codes.UNPROCESSABLE_CONTENT
    assert response.json()["detail"][0]["loc"] == ["header", "x-user-id"]
