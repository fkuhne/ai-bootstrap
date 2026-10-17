import httpx2
import pytest

from app.core.config import AppSettings
from app.llm.fake_llm_client import FakeLLMClient
from app.main import create_app
from tests.helpers import UseLLM

pytestmark = pytest.mark.anyio


async def test_liveness_answers_ok(client: httpx2.AsyncClient) -> None:
    response = await client.get("/api/health")

    assert response.status_code == httpx2.codes.OK
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize(
    ("llm_ready", "checks"), [(True, {"llm": "ok"}), (False, {"llm": "unavailable"})]
)
async def test_readiness_reports_the_llm(
    client: httpx2.AsyncClient, use_llm: UseLLM, llm_ready: bool, checks: dict[str, str]
) -> None:
    use_llm(FakeLLMClient(ready=llm_ready))

    response = await client.get("/api/health/ready")

    ready = set(checks.values()) == {"ok"}
    assert response.status_code == (httpx2.codes.OK if ready else httpx2.codes.SERVICE_UNAVAILABLE)
    assert response.json() == {"status": "ok" if ready else "unavailable", "checks": checks}


async def test_the_api_documents_itself_under_api(client: httpx2.AsyncClient) -> None:
    schema = (await client.get("/api/openapi.json")).json()

    assert schema["info"]["title"] == "ai-bootstrap"
    assert {"/api/health", "/api/health/ready"} <= set(schema["paths"])


async def test_the_docs_can_be_turned_off() -> None:
    app = create_app(AppSettings(docs_enabled=False))
    transport = httpx2.ASGITransport(app=app)
    async with httpx2.AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/api/docs")).status_code == httpx2.codes.NOT_FOUND
        assert (await client.get("/api/openapi.json")).status_code == httpx2.codes.NOT_FOUND
