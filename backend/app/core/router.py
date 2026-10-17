"""The /api/modules endpoint: which modules are on, so the web UI shows their pages
(docs/foundations.md#modules)."""

from fastapi import APIRouter, Request

from app.core.schemas import ModuleInfo, ModuleList

router = APIRouter(prefix="/modules", tags=["modules"])


@router.get(
    "",
    summary="The modules that are on",
    description="The modules the app's settings turn on, in the order the app lists them, "
    "whether or not they're ready: `/api/health/ready` says that.",
)
async def modules(request: Request) -> ModuleList:
    return ModuleList(
        modules=[ModuleInfo(name=module.name) for module in request.app.state.modules]
    )
