"""Adapter from the decision port to any System One endpoint: llama.cpp's server, TypeSafe or
OpenRouter (Adapter)."""

import httpx2
from pydantic import ValidationError

from app.core.errors import ServiceError
from app.core.services import (
    READINESS_TIMEOUT_SECONDS,
    json_or_none,
    status_error,
    timed_out,
    unreachable,
)
from app.modules.decision.decision_model import (
    Decision,
    DecisionModel,
    DecisionRequest,
    NoulQuestion,
)

# How the endpoint is named in errors.
SERVICE = "The decision endpoint"

# The smallest request: one yes-or-no question about a word.
READINESS_PROBE = DecisionRequest(
    state="ping", questions={"ready": NoulQuestion(type="noul", instructions="Is this a test?")}
)


class SystemOneClient(DecisionModel):
    """POSTs the request to `/systemone`, under the client's base URL, with the configured
    model unless the request names its own. The `http` client carries the base URL, the key
    and the timeout."""

    def __init__(self, http: httpx2.AsyncClient, *, model: str) -> None:
        self._http = http
        self._model = model

    async def decide(self, request: DecisionRequest) -> Decision:
        response = await self._post(request)
        try:
            return Decision.model_validate(response.json())
        except (ValueError, ValidationError) as error:
            raise ServiceError(f"{SERVICE} answered in an unknown shape.") from error

    async def is_ready(self) -> bool:
        """Ask the probe's question, tried once with a short timeout. A refusal counts as not
        ready, as a model that isn't a decision model or a wrong key is."""
        try:
            await self._post(READINESS_PROBE, probing=True)
        except ServiceError:
            return False
        return True

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _post(self, request: DecisionRequest, *, probing: bool = False) -> httpx2.Response:
        body = request.model_dump(mode="json", exclude_none=True)
        body.setdefault("model", self._model)
        try:
            if probing:
                response = await self._http.post(
                    "systemone", json=body, timeout=READINESS_TIMEOUT_SECONDS
                )
            else:
                response = await self._http.post("systemone", json=body)
        except httpx2.TimeoutException as error:
            raise timed_out(SERVICE) from error
        except httpx2.TransportError as error:
            raise unreachable(SERVICE) from error
        # llama.cpp answers 501 when its model isn't a decision model, or takes no images: a
        # refusal, as every status but those of a server that's down.
        if response.is_error:
            raise status_error(SERVICE, response.status_code, json_or_none(response.text))
        return response
