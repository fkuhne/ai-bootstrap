import pytest
from pydantic import ValidationError

from app.core.config import settings_of
from app.llm.config import LLMSettings


def test_defaults_reach_the_local_server_from_inside_compose() -> None:
    settings = LLMSettings()

    assert settings.provider == "openai-compatible"
    assert str(settings.base_url) == "http://llm:8080/v1"
    assert settings.model == "local"


def test_settings_come_from_llm_prefixed_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    monkeypatch.setenv("LLM_BASE_URL", "https://ollama.com/v1")
    monkeypatch.setenv("LLM_MODEL", "gemma4:31b")
    monkeypatch.setenv("LLM_MAX_RETRIES", "0")

    settings = LLMSettings()

    assert settings.provider == "fake"
    assert str(settings.base_url) == "https://ollama.com/v1"
    assert settings.model == "gemma4:31b"
    assert settings.max_retries == 0


def test_an_empty_value_means_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_MODEL", "")

    assert LLMSettings().model == "local"


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("LLM_PROVIDER", "ollama"),
        ("LLM_BASE_URL", "not a url"),
        ("LLM_TIMEOUT_SECONDS", "-1"),
        ("LLM_MAX_RETRIES", "-1"),
    ],
)
def test_invalid_values_are_rejected(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(ValidationError):
        LLMSettings()


def test_the_api_key_never_shows_in_the_settings_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_API_KEY", "sk-secret")

    settings = LLMSettings()

    assert "sk-secret" not in repr(settings)
    assert settings.api_key.get_secret_value() == "sk-secret"


def test_settings_are_read_once_and_cached() -> None:
    assert settings_of(LLMSettings) is settings_of(LLMSettings)


@pytest.mark.parametrize(
    ("value", "inputs"),
    [
        ("image, Audio", ["text", "image", "audio"]),
        ("video,text", ["text", "video"]),
        ("", None),  # unset: the server's model list says
    ],
)
def test_inputs_are_a_comma_separated_list(
    monkeypatch: pytest.MonkeyPatch, value: str, inputs: list[str] | None
) -> None:
    monkeypatch.setenv("LLM_INPUTS", value)

    assert LLMSettings().inputs == inputs


def test_an_unknown_input_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_INPUTS", "text,smell")

    with pytest.raises(ValidationError, match="unknown inputs: smell"):
        LLMSettings()
