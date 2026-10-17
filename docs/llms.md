# Use a model elsewhere

The backend reaches its model through any OpenAI-compatible API. By default that's the local llama.cpp server Docker Compose starts ([models.md](models.md) lists models for it). To use a model elsewhere, set four lines in `.env` (copy it from `.env.example`):

```
LLM_LOCAL_SERVER=0        # leave the local server out: no download, no memory used
LLM_BASE_URL=...          # the provider's OpenAI-compatible URL
LLM_API_KEY=...           # your key, from the provider's site
LLM_MODEL=...             # the model's name at that provider
```

Then `docker compose up -d --wait`, and check it with `docker compose run --rm llm-check`: it asks the model a question and prints the answer. `.env` is ignored by git, so the key stays on your machine.

## Providers

| Provider | `LLM_BASE_URL` | `LLM_MODEL`, for example | Notes |
|---|---|---|---|
| [Ollama Cloud](https://docs.ollama.com/cloud) | `https://ollama.com/v1` | `gemma4:31b` | A key from ollama.com/settings/keys. Takes `temperature`, `seed`, `reasoning_effort` and base64 images; not `tool_choice`. |
| [OpenAI](https://developers.openai.com/api/docs/models) | `https://api.openai.com/v1` | `gpt-6-luna` | Newer models want `max_completion_tokens` instead of `max_tokens`. |
| [Anthropic](https://platform.claude.com/docs/en/cli-sdks-libraries/libraries/openai-sdk) | `https://api.anthropic.com/v1/` | `claude-sonnet-5-5` | Anthropic calls this layer for testing, not production. It ignores `seed` and `response_format`, strips audio, and on current models refuses a `temperature` below 1. |
| [Google Gemini](https://ai.google.dev/gemini-api/docs/openai) | `https://generativelanguage.googleapis.com/v1beta/openai/` | a Gemini model name | |
| [OpenRouter](https://openrouter.ai/docs) | `https://openrouter.ai/api/v1` | `provider/model`, as OpenRouter lists it | Many providers behind one key. |
| llama.cpp on this machine, outside Docker | `http://host.docker.internal:8080/v1` | `local` | Uses the Mac's GPU through Metal, or a Windows GPU through llama.cpp's Vulkan build, where Docker can't. `LLM_API_KEY` stays empty. |

Ollama Cloud is the one this template has been run against, its live tests passing; the others are set as their documentation says, and haven't been called from it yet. Check yours with `docker compose run --rm llm-check` before relying on it. Any other provider with an OpenAI-compatible Chat Completions API works the same way. Model names change often: take them from the provider's own list.

## Images, audio and video

The web UI offers attachments for what the model takes, as `GET /api/llm/model` reports it. llama.cpp lists the inputs of the model it loaded, and OpenRouter lists each model's. Most other providers list their models without saying, so the backend assumes text alone: set `LLM_INPUTS` to what your model takes, for example `LLM_INPUTS=text,image` for Ollama Cloud's `gemma4:31b`. The setting also wins over what a server reports.

## Parameters

The backend sends the `parameters` of each chat request as given, and adds none of its own ([foundations](foundations.md#every-parameter-and-input)). Each provider accepts its own set, so a parameter that one takes, another may refuse: the error then carries the provider's reason, with status 502. A parameter a provider ignores has no effect.
