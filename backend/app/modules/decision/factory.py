"""Builds the decision model the settings ask for (Factory)."""

import httpx2

from app.modules.decision.config import DecisionSettings
from app.modules.decision.decision_model import DecisionModel
from app.modules.decision.fake_decision_model import FakeDecisionModel
from app.modules.decision.systemone_client import SystemOneClient


def create_decision_model(
    settings: DecisionSettings, *, transport: httpx2.AsyncBaseTransport | None = None
) -> DecisionModel:
    """The fake, or a System One client. Tests pass a mock `transport`, so no request leaves
    the process."""
    if settings.provider == "fake":
        return FakeDecisionModel()
    http = httpx2.AsyncClient(
        base_url=str(settings.base_url),
        headers={"Authorization": f"Bearer {settings.api_key.get_secret_value()}"},
        timeout=settings.timeout_seconds,
        transport=transport,
    )
    return SystemOneClient(http, model=settings.model)
