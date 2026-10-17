"""Requests and answers in the System One format, as llama.cpp's README shows them."""

from typing import Any

REQUEST: dict[str, Any] = {
    "state": "Customer message: I was charged twice for my order last week.",
    "questions": {
        "route": {
            "type": "choice",
            "instructions": "Which team should handle this?",
            "criteria": {"billing": None, "shipping": None, "technical": None},
        },
        "angry": {"type": "noul", "instructions": "Is the customer angry?"},
        "urgency": {
            "type": "score",
            "instructions": "How urgent is this?",
            "criteria": ["can wait", "this week", "today", "right now"],
        },
    },
}

ANSWER: dict[str, Any] = {
    "model": "openjev",
    "answers": {
        "route": {
            "type": "choice",
            "choice": "billing",
            "probabilities": {"billing": 0.9998, "shipping": 0.0001, "technical": 0.0001},
            "confidence": 0.9997,
        },
        "angry": {"type": "noul", "noul": 0.6328},
        "urgency": {
            "type": "score",
            "score": 2.0858,
            "legend": {"0": "can wait", "1": "this week", "2": "today", "3": "right now"},
            "probabilities": {"0": 0.0023, "1": 0.116, "2": 0.6753, "3": 0.2064},
            "confidence": 0.673,
        },
    },
    "usage": {"input_tokens": 239, "output_tokens": 0},
}
