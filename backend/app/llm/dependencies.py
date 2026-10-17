"""FastAPI dependencies of the LLM domain."""

from typing import Annotated, cast

from fastapi import Depends, Request

from app.llm.llm_client import LLMClient


async def get_llm_client(request: Request) -> LLMClient:
    """The LLM client the lifespan created for this application. Tests override this."""
    return cast(LLMClient, request.app.state.llm_client)


LLMClientDep = Annotated[LLMClient, Depends(get_llm_client)]
