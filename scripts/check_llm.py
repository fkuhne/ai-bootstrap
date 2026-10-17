"""Ask the LLM a question in each input it accepts, and report the answers.

Run it from the repo's root:

    docker compose run --rm llm-check

It talks to any OpenAI-compatible API, as the backend does: LLM_BASE_URL (by
default the local llama.cpp server), LLM_MODEL and LLM_API_KEY. It sends no
generation parameters, so the provider's defaults apply. It always asks in
text. When the server reports that the model also takes images or audio, it
sends a generated image or sound too. Other inputs it reports, such as video,
are listed but not tested. It exits with status 1 when any answer fails. It
uses only the standard library, so it runs in a plain Python image.
"""

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from media import red_square_png, tone_wav

# main() accepts only http and https, so opening this URL is safe (ruff's S310).
BASE_URL = (os.environ.get("LLM_BASE_URL") or "http://llm:8080/v1").rstrip("/")
# The local server serves the one model it loaded, whatever the name.
MODEL = os.environ.get("LLM_MODEL") or "local"
API_KEY = os.environ.get("LLM_API_KEY") or ""
TIMEOUT_SECONDS = 600


@dataclass(frozen=True)
class Probe:
    """One question, in one input, and a word its answer must contain."""

    name: str
    question: str
    attachment: dict[str, Any] | None
    expected: str | None


def probes(inputs: set[str]) -> list[Probe]:
    """The text question, plus one for each other input the model accepts."""
    found = [
        Probe(
            "text",
            "In one short sentence: what is the capital of France?",
            None,
            "paris",
        )
    ]
    if "image" in inputs:
        png = base64.b64encode(red_square_png()).decode()
        found.append(
            Probe(
                "image",
                "What color is this image? Answer with one word.",
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{png}"},
                },
                "red",
            )
        )
    if "audio" in inputs:
        wav = base64.b64encode(tone_wav()).decode()
        found.append(
            Probe(
                "audio",
                "What do you hear in this recording? Answer in a few words.",
                {"type": "input_audio", "input_audio": {"data": wav, "format": "wav"}},
                None,
            )
        )
    return found


def call(path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    """GET the path, or POST the body to it, and return the JSON reply."""
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"
    request = urllib.request.Request(  # noqa: S310
        f"{BASE_URL}{path}",
        data=None if body is None else json.dumps(body).encode(),
        headers=headers,
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310
        reply: dict[str, Any] = json.load(response)
        return reply


def model_inputs() -> set[str]:
    """The model's inputs, as the server reports them in its model list.

    The configured model is the one listed under its name, or the only one listed,
    as the local server lists the one it loaded. llama.cpp reports the inputs under
    `architecture`, as OpenRouter does. When nothing says, the check asks in text
    only.
    """
    try:
        models = call("/models").get("data") or []
    except urllib.error.URLError, TimeoutError, ValueError:
        return {"text"}
    named = [m for m in models if m.get("id") == MODEL]
    model = named[0] if named else models[0] if len(models) == 1 else {}
    reported = (model.get("architecture") or {}).get("input_modalities")
    return set(reported or model.get("input_modalities") or ["text"])


def speed(reply: dict[str, Any], seconds: float) -> str:
    """Describe the generation speed, from llama.cpp's timings when they're there."""
    timings = reply.get("timings")
    if timings:
        tokens, rate = timings["predicted_n"], timings["predicted_per_second"]
        return f"{tokens} tokens at {rate:.1f} tokens/s, {seconds:.1f} s in all"
    tokens = reply.get("usage", {}).get("completion_tokens")
    if tokens:
        return f"{tokens} tokens in {seconds:.1f} s"
    return f"{seconds:.1f} s"


def ask(probe: Probe) -> bool:
    """Ask one question, print what came back, and say whether it passed."""
    content: str | list[dict[str, Any]] = probe.question
    if probe.attachment:
        content = [{"type": "text", "text": probe.question}, probe.attachment]
    body = {"model": MODEL, "messages": [{"role": "user", "content": content}]}
    print(probe.name)
    print(f"  question:  {probe.question}")
    started = time.perf_counter()
    reply = call("/chat/completions", body)
    seconds = time.perf_counter() - started

    message = reply["choices"][0]["message"]
    print(f"  model:     {reply.get('model', 'not reported')}")
    answer = (message.get("content") or "").strip()
    # llama.cpp and DeepSeek name it reasoning_content; Ollama and OpenRouter, reasoning.
    reasoning = (message.get("reasoning_content") or message.get("reasoning") or "").strip()
    if reasoning:
        print(f"  reasoning: {len(reasoning)} characters before the answer")
    print(f"  answer:    {answer or '(empty)'}")
    print(f"  generated: {speed(reply, seconds)}")
    if not answer:
        print(f"FAILED: {probe.name}: the answer is empty")
        return False
    if probe.expected and probe.expected not in answer.lower():
        print(f"FAILED: {probe.name}: the answer doesn't mention '{probe.expected}'")
        return False
    return True


def main() -> int:
    if not BASE_URL.startswith(("http://", "https://")):
        print(f"FAILED: LLM_BASE_URL must be an http or https URL, not {BASE_URL!r}")
        return 1
    print(f"LLM check against {BASE_URL}")
    try:
        inputs = model_inputs()
        print(f"  model:  {MODEL}")
        print(f"  inputs: {', '.join(sorted(inputs))}")
        checked = probes(inputs)
        unchecked = inputs - {probe.name for probe in checked}
        if unchecked:
            print(f"  not checked: {', '.join(sorted(unchecked))}")
        results = [ask(probe) for probe in checked]
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")[:500]
        print(f"FAILED: the LLM answered HTTP {error.code}: {detail}")
        return 1
    except urllib.error.URLError as error:
        print(f"FAILED: can't reach the LLM: {error.reason}")
        return 1
    except TimeoutError:
        print(f"FAILED: no answer within {TIMEOUT_SECONDS} s")
        return 1

    if not all(results):
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
