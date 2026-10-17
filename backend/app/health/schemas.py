"""Response models of the health endpoints."""

from typing import Literal

from pydantic import BaseModel

CheckStatus = Literal["ok", "unavailable"]


class Liveness(BaseModel):
    """The process is up and serving requests."""

    status: Literal["ok"] = "ok"


class Readiness(BaseModel):
    """Whether every dependency can serve requests, with one entry per dependency."""

    status: CheckStatus
    checks: dict[str, CheckStatus]
