"""The decision port: typed questions about a state, answered with probabilities, in the System
One format that llama.cpp's server, TypeSafe and OpenRouter share
(docs/foundations.md#the-decision-model).

A question is `noul` (yes or no), `choice` (one of named options) or `score` (a level on a scale).
Fields a provider adds, to a request or an answer, pass through as given.
"""

from typing import Annotated, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, JsonValue

# A question's text, or an object or array that reaches the model as JSON.
Instructions = str | dict[str, JsonValue] | list[JsonValue]


class _Format(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)


class NoulCriteria(_Format):
    """What yes and no mean, when the question alone doesn't say."""

    true: str | None = None
    false: str | None = None


class NoulQuestion(_Format):
    """Yes or no, answered with the probability of yes."""

    type: Literal["noul"]
    instructions: Instructions
    criteria: NoulCriteria | None = None


class ChoiceQuestion(_Format):
    """One of the named options, each with a description or null."""

    type: Literal["choice"]
    instructions: Instructions
    criteria: dict[str, str | None] = Field(min_length=2)


class ScoreQuestion(_Format):
    """A level on a scale of 2 to 10 levels, described lowest first."""

    type: Literal["score"]
    instructions: Instructions
    criteria: list[str] = Field(min_length=2, max_length=10)


Question = Annotated[NoulQuestion | ChoiceQuestion | ScoreQuestion, Field(discriminator="type")]


class DecisionRequest(_Format):
    """What to decide about, and the questions to answer, each under a name of the caller's."""

    model_config = ConfigDict(
        extra="allow",
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "state": "Customer: I was charged twice for my order, and nobody replied.",
                    "questions": {
                        "angry": {"type": "noul", "instructions": "Is the customer angry?"},
                        "team": {
                            "type": "choice",
                            "instructions": "Which team should handle this?",
                            # Descriptions, not nulls: the published schema drops null values,
                            # which would leave no options.
                            "criteria": {
                                "billing": "Payments, refunds and invoices",
                                "shipping": "Deliveries and returns",
                                "technical": "The website and the app",
                            },
                        },
                        "urgency": {
                            "type": "score",
                            "instructions": "How urgent is this?",
                            "criteria": ["can wait", "this week", "today", "right now"],
                        },
                    },
                }
            ]
        },
    )

    state: JsonValue = Field(
        description="What to decide about: text, or an object or array, which reaches the "
        "model as JSON."
    )
    files: list[str] | None = Field(
        default=None,
        description="Images, or sounds for models that take them, as data URLs.",
    )
    questions: dict[str, Question] = Field(min_length=1)


class NoulAnswer(_Format):
    type: Literal["noul"]
    noul: float = Field(description="The probability that the answer is yes.")


class ChoiceAnswer(_Format):
    type: Literal["choice"]
    choice: str = Field(description="The most likely option.")
    probabilities: dict[str, float] = Field(description="Each option's, summing to 1.")
    confidence: float = Field(description="From 0, every option equally likely, to 1.")


class ScoreAnswer(_Format):
    type: Literal["score"]
    score: float = Field(description="The expected level's index; it may fall between two.")
    legend: dict[str, str] = Field(description="Each level's description, by index.")
    probabilities: dict[str, float] = Field(description="Each level's, summing to 1.")
    confidence: float = Field(description="From 0 to 1.")


Answer = Annotated[NoulAnswer | ChoiceAnswer | ScoreAnswer, Field(discriminator="type")]


class DecisionUsage(_Format):
    input_tokens: int
    output_tokens: int


class Decision(_Format):
    """The answers, under the questions' names, and the model that gave them."""

    model: str
    answers: dict[str, Answer]
    usage: DecisionUsage | None = None


class DecisionModel(Protocol):
    """A decision model the backend can call. Implementations are interchangeable (Strategy).

    Every method raises the core's `ServiceError`s on failure (`app.core.errors`).
    """

    async def decide(self, request: DecisionRequest) -> Decision:
        """Answer the request's questions about its state."""
        ...

    async def is_ready(self) -> bool:
        """Tell whether the model can take requests right now."""
        ...

    async def aclose(self) -> None:
        """Release connections and other resources."""
        ...
