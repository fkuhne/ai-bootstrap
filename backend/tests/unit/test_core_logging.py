"""One log format for every line, in the local time zone, without the health-check noise."""

import logging
import time
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest

from app.core.logging import (
    REQUEST_LOGGERS,
    UVICORN_LOGGERS,
    LocalTimeFormatter,
    QuietHealthChecks,
    configure_logging,
)


@pytest.fixture
def sao_paulo(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("TZ", "America/Sao_Paulo")
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


@pytest.fixture(autouse=True)
def default_logging() -> Iterator[None]:
    yield
    configure_logging("INFO")  # as the other tests expect it


def record(args: object, msg: str = '%s - "%s %s HTTP/%s" %d') -> logging.LogRecord:
    return logging.LogRecord("uvicorn.access", logging.INFO, __file__, 1, msg, args, None)  # type: ignore[arg-type]


@pytest.mark.usefixtures("sao_paulo")
def test_times_are_local_with_their_offset() -> None:
    line = record(None, "hello")
    line.created = datetime(2026, 10, 3, tzinfo=UTC).timestamp() + 0.123  # midnight UTC

    assert LocalTimeFormatter().formatTime(line) == "2026-10-02T21:00:00.123-03:00"
    assert LocalTimeFormatter().formatTime(line, "%H:%M %z") == "21:00 -0300"


@pytest.mark.parametrize(
    ("args", "kept"),
    [
        (("127.0.0.1:50288", "GET", "/api/health", "1.1", 200), False),  # Docker's check
        (("127.0.0.1:50288", "GET", "/api/health", "1.1", 503), True),  # a failing one stays
        (("172.18.0.1:58198", "POST", "/api/chat", "1.1", 200), True),
        (None, True),  # not an access record
    ],
)
def test_successful_health_checks_are_dropped(args: object, kept: bool) -> None:
    assert QuietHealthChecks().filter(record(args)) is kept


def test_every_logger_shares_one_format_and_requests_stay_quiet() -> None:
    configure_logging("INFO")

    root = logging.getLogger()
    assert isinstance(root.handlers[0].formatter, LocalTimeFormatter)
    for name in UVICORN_LOGGERS:
        assert logging.getLogger(name).handlers == []
        assert logging.getLogger(name).propagate
    for name in REQUEST_LOGGERS:
        assert logging.getLogger(name).level == logging.WARNING
    access = logging.getLogger("uvicorn.access")
    assert [type(f) for f in access.filters].count(QuietHealthChecks) == 1


def test_debug_shows_the_requests_and_the_health_checks() -> None:
    configure_logging("INFO")
    configure_logging("DEBUG")

    for name in REQUEST_LOGGERS:
        assert logging.getLogger(name).level == logging.DEBUG
    access = logging.getLogger("uvicorn.access")
    assert not any(isinstance(f, QuietHealthChecks) for f in access.filters)
