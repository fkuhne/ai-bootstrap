"""A deterministic decision model, for tests and for running the module without a model."""

from app.modules.decision.decision_model import (
    Answer,
    ChoiceAnswer,
    ChoiceQuestion,
    Decision,
    DecisionModel,
    DecisionRequest,
    DecisionUsage,
    NoulAnswer,
    NoulQuestion,
    Question,
    ScoreAnswer,
)


class FakeDecisionModel(DecisionModel):
    """Answers as a model that knows nothing would: yes at 0.5, and every option and level
    equally likely, so the first option and the middle of the scale.

    `DECISION_PROVIDER=fake` selects it.
    """

    model = "fake"

    def __init__(self, *, ready: bool = True) -> None:
        self._ready = ready
        self.closed = False

    async def decide(self, request: DecisionRequest) -> Decision:
        return Decision(
            model=self.model,
            answers={name: _answer(question) for name, question in request.questions.items()},
            usage=DecisionUsage(input_tokens=0, output_tokens=0),
        )

    async def is_ready(self) -> bool:
        return self._ready

    async def aclose(self) -> None:
        self.closed = True


def _answer(question: Question) -> Answer:
    match question:
        case NoulQuestion():
            return NoulAnswer(type="noul", noul=0.5)
        case ChoiceQuestion():
            options = list(question.criteria)
            return ChoiceAnswer(
                type="choice",
                choice=options[0],
                probabilities=dict.fromkeys(options, 1 / len(options)),
                confidence=0.0,
            )
        case _:
            levels = question.criteria
            return ScoreAnswer(
                type="score",
                score=(len(levels) - 1) / 2,
                legend={str(index): level for index, level in enumerate(levels)},
                probabilities={str(index): 1 / len(levels) for index in range(len(levels))},
                confidence=0.0,
            )
