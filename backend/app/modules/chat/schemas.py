"""Request and event models of the /api/chat endpoints.

Answers and stream parts are the LLM port's own models (`Completion`, `ContentDelta`,
`ReasoningDelta`, `StreamEnd`): there's nothing to reshape.
"""

from pydantic import BaseModel, ConfigDict, Field

from app.llm.llm_client import ChatMessage, RequestParameters


class ChatRequest(BaseModel):
    """The conversation so far, and any generation parameters for the model."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "messages": [{"role": "user", "content": "In one sentence, what is an LLM?"}],
                    "parameters": {
                        "max_tokens": 512,
                        "reasoning_effort": "none",
                    },
                }
            ]
        }
    )

    messages: list[ChatMessage] = Field(min_length=1)
    parameters: RequestParameters = Field(default_factory=dict)
