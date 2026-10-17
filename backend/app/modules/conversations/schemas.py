"""Request and event models of the /api/conversations endpoints. The JSON responses are the
store's records."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.llm.llm_client import Content, RequestParameters, Usage


class AskRequest(BaseModel):
    """A question in a conversation. The history is the conversation's own."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "content": "In one sentence, what is an LLM?",
                    "parameters": {"max_tokens": 512},
                }
            ]
        }
    )

    content: Content = Field(
        description="Text, or a list of parts with text, images, audio or video."
    )
    parameters: RequestParameters = Field(default_factory=dict)


class ConversationDoneEvent(BaseModel):
    """Data of the `done` event of an answer streamed in a conversation: how it ended, and the
    ids the question and the answer were stored under."""

    model: str
    finish_reason: str | None
    usage: Usage | None
    question_id: UUID
    answer_id: UUID
