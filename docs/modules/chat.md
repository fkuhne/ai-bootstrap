# The chat module

Chat asks the LLM with the conversation the caller sends, and returns the answer whole or streamed as it's written. The backend keeps nothing: each call carries the conversation so far, a system prompt and earlier turns included. To have the backend keep conversations, use [the conversations module](conversations.md). Why it's built this way is in [the foundations](../foundations.md#chat-whole-or-streamed).

Chat has no service of its own: it asks the core's LLM, whichever model `LLM_*` sets.

**Its page,** Chat in the web UI's sidebar, keeps the conversation in the browser until you reload it or start a new chat; only complete answers join it. With the conversations module on, conversations' page, which the backend stores, takes its place.

## Try it

With the stack up (`docker compose up -d --wait`):

```
docker compose run --rm chat-demo
docker compose run --rm chat-demo "Your own question"
```

The demo asks for a whole answer, a conversation with a system prompt and earlier turns, a streamed answer, and an answer about an image. It prints each call, so you can copy them into any language. `CHAT_DEMO_PARAMETERS`, a JSON object such as `{"temperature": 0.7}`, adds generation parameters to each. The API's own page, http://127.0.0.1:8000/api/docs, lets you try the endpoints in the browser.

## The calls

- **`POST /api/chat`** returns the whole answer, with the model's reasoning apart when it shows it.
- **`POST /api/chat/stream`** sends server-sent events: `reasoning` and `token` pieces, then `done` with the model, the finish reason and the usage. A failure once the stream has started ends it with an `error` event. Closing the stream stops the model.

Both take `{"messages": [...], "parameters": {...}}`. A message's content is text, or parts with images, audio and video when the model takes them, as `GET /api/llm/model` tells. `parameters` takes anything the model accepts, such as `temperature`, `seed` or `reasoning_effort`.

## Turn it off, or remove it

- **Off:** `CHAT_ENABLED=0` removes its endpoints.
- **Removed:** as [the recipe](README.md#remove-a-module) says. The core's `scripts/demo.py` and `scripts/media.py`, which its demo uses, stay.
