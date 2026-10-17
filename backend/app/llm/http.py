"""The statuses an endpoint that calls the LLM answers on failure, for the API's documentation;
the core's handler answers them (docs/foundations.md#errors)."""

from fastapi import status

from app.core.errors import described

LLM_ERROR_RESPONSES = described(
    {
        status.HTTP_429_TOO_MANY_REQUESTS: "The LLM endpoint is rate-limiting",
        status.HTTP_502_BAD_GATEWAY: "The LLM endpoint refused the request",
        status.HTTP_503_SERVICE_UNAVAILABLE: "The LLM endpoint can't be reached, or is down",
        status.HTTP_504_GATEWAY_TIMEOUT: "The LLM endpoint didn't answer in time",
    }
)
