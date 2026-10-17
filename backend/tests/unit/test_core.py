import logging
from collections.abc import Iterator

import pytest
from fastapi import APIRouter
from pydantic import ValidationError
from pydantic_settings import SettingsConfigDict

from app.core.config import AppSettings, ModuleSettings, forget_settings, settings_of
from app.core.logging import configure_logging
from app.core.modules import Module


@pytest.fixture
def restore_root_logger() -> Iterator[None]:
    root = logging.getLogger()
    level, handlers = root.level, root.handlers[:]
    yield
    root.setLevel(level)
    root.handlers[:] = handlers


def test_defaults() -> None:
    settings = AppSettings()

    assert (settings.name, settings.log_level, settings.docs_enabled) == (
        "ai-bootstrap",
        "INFO",
        True,
    )


def test_settings_come_from_app_prefixed_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("APP_DOCS_ENABLED", "false")

    settings = AppSettings()

    assert settings.log_level == "DEBUG"
    assert settings.docs_enabled is False


@pytest.mark.parametrize("value", ["debug", "Debug"])
def test_the_log_level_ignores_case(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("APP_LOG_LEVEL", value)

    assert AppSettings().log_level == "DEBUG"


def test_an_empty_value_means_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_LOG_LEVEL", "")

    assert AppSettings().log_level == "INFO"


def test_unknown_log_level_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_LOG_LEVEL", "LOUD")

    with pytest.raises(ValidationError):
        AppSettings()


def test_settings_are_read_once_and_kept_until_forgotten(monkeypatch: pytest.MonkeyPatch) -> None:
    first = settings_of(AppSettings)
    monkeypatch.setenv("APP_NAME", "another")

    assert settings_of(AppSettings) is first
    forget_settings()
    assert settings_of(AppSettings).name == "another"


@pytest.mark.usefixtures("restore_root_logger")
def test_configure_logging_sets_the_root_level() -> None:
    configure_logging("WARNING")

    assert logging.getLogger().level == logging.WARNING


class EchoSettings(ModuleSettings):
    """A module's settings, as each module writes them: its prefix, and its own fields."""

    model_config = SettingsConfigDict(env_prefix="ECHO_")

    word: str = "hello"


def test_a_module_s_switch_is_its_prefix_s_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    assert EchoSettings().enabled is True

    monkeypatch.setenv("ECHO_ENABLED", "0")

    assert EchoSettings().enabled is False


def test_a_module_s_settings_share_the_core_s_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    # An empty value is the default, and the other domains' variables are ignored.
    monkeypatch.setenv("ECHO_WORD", "")
    monkeypatch.setenv("ECHO_ENABLED", "")
    monkeypatch.setenv("ECHO_SOMETHING_ELSE", "x")

    settings = EchoSettings()

    assert (settings.word, settings.enabled) == ("hello", True)


def test_a_module_reads_its_switch_from_the_settings_it_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    echo = Module(name="echo", router=APIRouter(), settings=EchoSettings)
    assert echo.enabled() is True

    monkeypatch.setenv("ECHO_ENABLED", "0")
    forget_settings()

    assert echo.enabled() is False
