"""Health endpoints: liveness for the process, readiness for its dependencies."""

import asyncio

from fastapi import APIRouter, Request, Response, status

from app.health.schemas import CheckStatus, Liveness, Readiness
from app.llm.dependencies import LLMClientDep

router = APIRouter(prefix="/health", tags=["health"])


@router.get(
    "",
    summary="Liveness",
    description="Answers while the process is up. It checks no dependencies.",
)
async def liveness() -> Liveness:
    return Liveness()


@router.get(
    "/ready",
    summary="Readiness",
    description="Checks every dependency at once: the LLM, and each module that's on. "
    "Answers 503 while one of them is unavailable.",
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": Readiness}},
)
async def readiness(llm: LLMClientDep, request: Request, response: Response) -> Readiness:
    # At once, so a service that hangs until its timeout holds the answer only that long.
    probes = {"llm": llm.is_ready()} | {
        module.name: module.is_ready(request)
        for module in request.app.state.modules
        if module.is_ready is not None
    }
    results = await asyncio.gather(*probes.values())
    checks: dict[str, CheckStatus] = {
        name: "ok" if ready else "unavailable" for name, ready in zip(probes, results, strict=True)
    }
    ready = all(check == "ok" for check in checks.values())
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return Readiness(status="ok" if ready else "unavailable", checks=checks)
