"""Logging configuration: one format for every line, the server's own included."""

import logging
from datetime import datetime

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"

# Uvicorn's loggers, which it configures with its own handlers before importing the app.
UVICORN_LOGGERS = ("uvicorn", "uvicorn.error", "uvicorn.access")
# HTTP clients that log every request, to the LLM among others: detail for DEBUG only.
REQUEST_LOGGERS = ("httpx", "httpx2")
# The liveness endpoint, which Docker's health check calls every 30 seconds.
HEALTH_PATH = "/api/health"


class LocalTimeFormatter(logging.Formatter):
    """Times in ISO 8601, in the local time zone with its offset, to the millisecond:
    `2026-10-03T12:33:14.123-03:00`. The zone is the process's, which `TZ` sets; UTC in a
    container without it."""

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:  # noqa: N802
        moment = datetime.fromtimestamp(record.created).astimezone()
        return moment.strftime(datefmt) if datefmt else moment.isoformat(timespec="milliseconds")


class QuietHealthChecks(logging.Filter):
    """Drops the access lines of successful liveness checks, which would fill the log."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if not isinstance(args, tuple) or len(args) != 5:
            return True
        # Uvicorn's access record: (client, method, path, HTTP version, status).
        return not (args[2] == HEALTH_PATH and args[4] == 200)


def configure_logging(level: str) -> None:
    """Send every log record to stderr at `level`, in one format, replacing any earlier
    configuration, uvicorn's included. Below DEBUG, health checks and each HTTP request the
    backend makes stay out of the log."""
    handler = logging.StreamHandler()
    handler.setFormatter(LocalTimeFormatter(LOG_FORMAT))
    logging.basicConfig(level=level, handlers=[handler], force=True)
    for name in UVICORN_LOGGERS:
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True
    detailed = logging.getLevelName(level) <= logging.DEBUG
    for name in REQUEST_LOGGERS:
        logging.getLogger(name).setLevel(logging.DEBUG if detailed else logging.WARNING)
    access = logging.getLogger("uvicorn.access")
    for old in [f for f in access.filters if isinstance(f, QuietHealthChecks)]:
        access.removeFilter(old)
    if not detailed:
        access.addFilter(QuietHealthChecks())
