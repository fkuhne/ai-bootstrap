"""The OpenAI SDK's errors as the core's, for every adapter on an OpenAI-compatible API: the
LLM's, and RAG's embeddings (docs/foundations.md#errors)."""

import openai

from app.core.errors import ServiceError
from app.core.services import status_error, timed_out, unreachable


def translate(error: openai.APIError, service: str) -> ServiceError:
    """The SDK's error, for `service`, such as "The LLM endpoint"."""
    # APITimeoutError subclasses APIConnectionError, so it must be checked first.
    if isinstance(error, openai.APITimeoutError):
        return timed_out(service)
    if isinstance(error, openai.APIConnectionError):
        return unreachable(service)
    if isinstance(error, openai.APIStatusError):
        return status_error(service, error.status_code, error.body)
    return ServiceError(f"{service} failed.")
