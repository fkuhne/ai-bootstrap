import pytest

from app.llm.fake_llm_client import FakeLLMClient
from app.main import create_app

pytestmark = pytest.mark.anyio


async def test_the_lifespan_creates_the_clients_and_closes_them(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    app = create_app(modules=())

    async with app.router.lifespan_context(app):
        client = app.state.llm_client
        assert isinstance(client, FakeLLMClient)
        assert not client.closed

    assert client.closed
    # The app's own logging, which replaces pytest's handlers, writes to stderr.
    logged = capsys.readouterr().err
    assert "INFO app.main: Ready: model 'local' (fake) at http://llm:8080/v1." in logged
