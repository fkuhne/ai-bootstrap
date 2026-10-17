"""The /api/llm endpoints: the configured model, for any page that talks to it."""

from fastapi import APIRouter

from app.llm.dependencies import LLMClientDep
from app.llm.http import LLM_ERROR_RESPONSES
from app.llm.llm_client import ModelInfo

router = APIRouter(prefix="/llm", tags=["llm"])


@router.get(
    "/model",
    summary="The model, and the inputs it accepts",
    description="The model that answers, and what a message to it may carry: text, and "
    "images, audio or video when the model takes them, as its server reports them or "
    "`LLM_INPUTS` says. The web UI offers attachments for those.",
    responses=LLM_ERROR_RESPONSES,
)
async def model(llm: LLMClientDep) -> ModelInfo:
    return await llm.model_info()
