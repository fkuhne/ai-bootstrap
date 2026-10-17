"""Models every domain's API shares."""

from pydantic import BaseModel, Field


class ErrorEvent(BaseModel):
    """Data of an `error` event: a streamed answer failed after the stream had started."""

    status: int = Field(
        description="The HTTP status the same request answers without streaming: 503 when the "
        "LLM, or a service the module uses, can't be reached; 504 when the LLM didn't answer in "
        "time; 429 when its provider is rate-limiting requests; 502 when it rejected the "
        "request; 404 when what the request was about is gone, such as a deleted conversation."
    )
    detail: str


class ModuleInfo(BaseModel):
    """A module that's on."""

    name: str = Field(description="Its name, as its readiness check and its settings call it.")


class ModuleList(BaseModel):
    """The modules that are on, in the order the app lists them."""

    modules: list[ModuleInfo]
