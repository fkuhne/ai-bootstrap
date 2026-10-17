# ai-bootstrap

A starting point for AI apps, and a way to build them with your coding agent. One command starts a working chat app:
- a FastAPI backend;
- a React web UI that streams answers and keeps conversations;
- PostgreSQL;
- an LLM reached through any OpenAI-compatible API, run on your machine by default, or in the cloud.

Then you describe your app in `spec/`, and your agent builds it in small, reviewed steps, recording every decision.

Everything is plain code you can read and change, tested, with CI on GitHub Actions running the same checks you run. It runs on Linux and macOS, on the CPU, and it's made for Windows, NVIDIA GPUs and, through Vulkan, AMD and Intel ones too, which haven't been run yet. It needs no paid service. What it's made of, and why, is in [docs/foundations.md](docs/foundations.md).

## Quick start

You need Docker (Engine 25 or later) with Compose v2.

```
docker compose up -d --wait
```

Open http://127.0.0.1:3000. The first start downloads the default models, 3.4 GB for the chat, 0.45 GB for the decision model and 0.31 GB for the embeddings, which can take several minutes; the page opens at once and says what isn't ready yet. `docker compose down` stops everything, and the model stays cached for the next start.

**Docker needs about 8 GB of memory for all of it:** the chat model alone took more than 4.5 GB at its default context, the decision model up to 1.7 GB, and the embedding model up to 1.5 GB. With less, the chat model is killed for memory, and stays down until the next `docker compose up -d`. Give Docker more memory, in Docker Desktop's settings or with `colima start --memory 8`; turn off the modules you don't need, such as `DECISION_ENABLED=0`; lower `LLM_CONTEXT_SIZE`; pick a smaller model from [docs/models.md](docs/models.md); or use a model elsewhere.

To try it without a model, put `LLM_PROVIDER=fake` and `LLM_LOCAL_SERVER=0` in a `.env` file: the app answers "Fake answer to: …" in seconds.

## Start your app

1. Click **Use this template** on GitHub, or clone the repository.
2. Open it in your coding agent: Claude Code, Codex, Cursor, GitHub Copilot, Gemini CLI, or any agent that reads `AGENTS.md`.
3. Ask it to **start the app**, or run the `start-app` skill (`/start-app` in Claude Code). It interviews you about your app, then writes:
   - its product spec, `spec/product.md`;
   - its first requirements, `spec/requirements.md`;
   - its first plan, `spec/plan.md`;
   - its name.

From then on, the agent works through the plan one step at a time:
- **Before each choice,** it lays out the options, the evidence and a recommendation, and you pick. The `next-step` skill does this.
- **Each choice** gets a record in `spec/decisions/`; the `decide` skill writes it.
- **Each step** lands in small commits, with its tests.
- **A new capability** an app may not need becomes a module, by [a recipe](docs/modules/README.md); the `add-module` skill walks through it.

`AGENTS.md` holds the method and the commands, and [the foundations](docs/foundations.md#the-method) explain it.

## Choose a model

**On your machine (the default).** llama.cpp's server runs the model on the CPU. Set `LLM_GPU=nvidia` for an NVIDIA GPU (Linux with the NVIDIA Container Toolkit, or Windows with Docker Desktop), or `vulkan` for an AMD or Intel GPU on Linux. Neither variant has been run on a GPU yet, nor the template on Windows. `LLM_HF_MODEL` picks the model; [docs/models.md](docs/models.md) suggests five, from 2 to 7 GB, with images, audio or video.

**Elsewhere.** Set `LLM_LOCAL_SERVER=0`, then the provider's `LLM_BASE_URL`, `LLM_API_KEY` and `LLM_MODEL`. [docs/llms.md](docs/llms.md) gives them for Ollama Cloud, OpenAI, Anthropic, Google Gemini, OpenRouter, and llama.cpp run outside Docker. Many cloud providers don't say which inputs a model takes: set `LLM_INPUTS`, such as `text,image`, to get attachments in the web UI.

**Check it:**

```
docker compose run --rm llm-check
```

It asks the model a question in each input it accepts, and prints the answers and the speed.

## What you get

**The web UI**, at http://127.0.0.1:3000, laid out like llama.cpp's own: a page for each module that's on, chosen in the sidebar, each one saying what it needs and isn't ready yet. Answers stream in after the model's reasoning, which shows in a box while it's written. A dropdown beside the model's name sets how much the model reasons; the round button stops an answer; a paperclip attaches images, audio or video when the model takes them.

**The API**, under http://127.0.0.1:8000/api, documented at http://127.0.0.1:8000/api/docs. The core's endpoints are these; each module adds its own, listed in [its section](#modules) below.

| Endpoint | What it does |
|---|---|
| `GET /api/llm/model` | The model, and the inputs it accepts |
| `GET /api/modules` | The modules that are on, whose pages the web UI shows |
| `GET /api/health`, `/api/health/ready` | Liveness, and readiness of the LLM and each module |

A message's content is text, or parts with images, audio and video. `parameters` takes anything the model accepts, such as `temperature`, `seed` or `reasoning_effort`. What a user stores belongs to an anonymous id the browser sends as `X-User-Id`; an app that adds login replaces one function ([foundations](docs/foundations.md#users)).

## Settings

Every setting is an environment variable with a working default, so `.env` is optional. Copy `.env.example` to `.env` and change what you need; `.env.example` explains each one. These are the core's; each module's are in [its section](#modules) below.

| Setting | Default | What it sets |
|---|---|---|
| `LLM_LOCAL_SERVER` | `1` | `0` leaves the local LLM server out |
| `LLM_GPU` | `cpu` | The local server's variant: `cpu`, `nvidia` or `vulkan` |
| `LLM_HF_MODEL` | `unsloth/Qwen3.5-4B-GGUF:Q4_K_M` | The local model, from Hugging Face |
| `LLM_CONTEXT_SIZE` | `8192` | The local model's context window, in tokens |
| `LLM_PORT` | `8080` | The local server's port, with its own chat page |
| `LLM_PROVIDER` | `openai-compatible` | `fake` answers without a model |
| `LLM_BASE_URL` | `http://llm:8080/v1` | The OpenAI-compatible API to use |
| `LLM_API_KEY` | (none) | Its key |
| `LLM_MODEL` | `local` | The model's name there |
| `LLM_INPUTS` | (from the server) | What the model takes, such as `text,image` |
| `LLM_TIMEOUT_SECONDS` | `300` | How long to wait for an answer |
| `LLM_MAX_RETRIES` | `2` | Retries of a request that failed before reaching the model |
| `APP_NAME` | `ai-bootstrap` | The app's name, in the API and the web UI |
| `APP_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING` or `ERROR` |
| `APP_DOCS_ENABLED` | `true` | The API's documentation at `/api/docs` |
| `TZ` | `UTC` | The time zone of the backend's log times |
| `BACKEND_PORT` | `8000` | The API's port |
| `FRONTEND_PORT` | `3000` | The web UI's port |
| `CHAT_DEMO_PARAMETERS` | (none) | Parameters the chat and conversations demos add to each question, as JSON |

Every port is published on `127.0.0.1` only. A setting given in the shell, as in `LLM_PROVIDER=fake docker compose up -d`, lasts for that command only: put lasting settings in `.env`. The web UI takes `APP_NAME` when its image is built, so after changing it run `docker compose up -d --build`.

## Develop

The checks run in Docker, the same on every system, and CI runs the same commands:

```
docker compose run --rm backend-checks
docker compose run --rm frontend-checks
```

- **The backend's checks:** ruff, mypy strict, import rules, and pytest with at least 90% coverage. Tests against the running services are left out of them; run those with `docker compose run --rm backend-checks pytest -m integration --no-cov`.
- **The web UI's checks:** oxlint, Prettier, TypeScript, the API's types and Vitest. `docker compose run --rm frontend-checks npm run format` formats `frontend/src/`.
- **After an endpoint or an API model changes,** regenerate the schema, then the web UI's types, and commit both:

  ```
  docker compose run --rm backend-checks python -m app.openapi
  docker compose run --rm frontend-checks npm run api:types
  ```
- **Hot reload for the web UI,** with Node 24 on your machine: `npm --prefix frontend install`, then `npm --prefix frontend run dev`. It serves the app on http://localhost:5173, and forwards `/api` to the backend.

The backend is laid out by domain in `backend/app/`, the web UI by feature in `frontend/src/`; [the foundations](docs/foundations.md#the-backends-layout-and-gates) explain both.

## Modules

A capability an app may not need is built as a module: its own services if it has any, with a switch to turn it off, which an app keeps or deletes. So an app carries only what it uses ([foundations](docs/foundations.md#modules)). [docs/modules/](docs/modules/README.md) lists them, and says how to add one, place by place, or remove one.

### Chat

Chat asks the model with the conversation the caller sends, whole or streamed; the backend keeps nothing. **Its page,** Chat, keeps the conversation in the browser until you reload it or start a new chat; with the conversations module on, conversations' page takes its place. [Its page](docs/modules/chat.md) shows the calls.

| Endpoint | What it does |
|---|---|
| `POST /api/chat`, `/api/chat/stream` | Sends a conversation to the model; returns the whole answer, or streams it as server-sent events (`reasoning`, `token`, then `done`) |

| Setting | Default | What it sets |
|---|---|---|
| `CHAT_ENABLED` | `1` | `0` turns the chat module off |

```
docker compose run --rm chat-demo
docker compose run --rm chat-demo "Your own question"
```

### Conversations

Conversations keeps each user's conversations in PostgreSQL, and asks in them with their stored history; it brings the database and its migrations with it. **Its page,** Chat, lists your conversations by day, and deletes one after asking. **PostgreSQL** is at `127.0.0.1:5433` for your own tools, and a `migrate-db` job brings the tables up to date at every start. [Its page](docs/modules/conversations.md) shows the calls and the database.

| Endpoint | What it does |
|---|---|
| `GET`, `POST /api/conversations` | Lists the user's conversations, or starts one |
| `GET`, `DELETE /api/conversations/{id}` | Opens a conversation with its messages, or deletes it |
| `POST /api/conversations/{id}/messages`, `…/stream` | Asks in a conversation: the backend adds the stored history, and stores the turn once the answer is complete |

| Setting | Default | What it sets |
|---|---|---|
| `CONVERSATIONS_ENABLED` | `1` | `0` turns the conversations module off, with its database |
| `CONVERSATIONS_LOCAL_DATABASE` | `CONVERSATIONS_ENABLED`'s | `0` leaves the local PostgreSQL out, for a database elsewhere |
| `POSTGRES_PASSWORD` | `app-local` | The database's password, set when its volume is first created |
| `POSTGRES_PORT` | `5433` | The database's port |
| `DATABASE_URL` | (the local PostgreSQL) | Another database, as a SQLAlchemy URL |

```
docker compose run --rm conversations-demo
```

After a change to its tables, with the stack up, write their migration:

```
docker compose run --rm backend-checks alembic revision --autogenerate -m "what changed"
```

### The decision model

The decision model answers typed questions about a text with probabilities, for an agent's routing and for classification: is this a complaint, which team should take it, how urgent is it. Locally, llama.cpp runs Laya, a 0.45 GB model; in the cloud, TypeSafe or OpenRouter. **Its page,** Decide, asks questions about a text, yes or no, one of options, or a level on a scale, and shows the answers as probability bars. [Its page](docs/modules/decision.md) gives the format, the models and the providers.

| Endpoint | What it does |
|---|---|
| `POST /api/decide` | Answers typed questions about a text with probabilities (yes or no, one of named options, a level on a scale) |

| Setting | Default | What it sets |
|---|---|---|
| `DECISION_ENABLED` | `1` | `0` turns the decision module off, with its local server |
| `DECISION_PROVIDER` | `systemone` | Which decision model answers: `systemone`, or `fake` |
| `DECISION_LOCAL_SERVER` | `DECISION_ENABLED`'s | `0` leaves the local decision server out |
| `DECISION_GPU` | `LLM_GPU`'s | The local decision server's variant |
| `DECISION_HF_MODEL` | `ggml-org/Laya-GGUF:Q8_0` | The local decision model, from Hugging Face |
| `DECISION_CONTEXT_SIZE` | `8192` | The longest text it reads at once, in tokens |
| `DECISION_PORT` | `8081` | The local decision server's port |
| `DECISION_BASE_URL` | `http://decision:8080/v1` | Its System One endpoint |
| `DECISION_API_KEY` | (none) | Its key |
| `DECISION_MODEL` | `local` | The decision model's name there |
| `DECISION_TIMEOUT_SECONDS` | `60` | How long to wait for its answers |

```
docker compose run --rm decision-demo
```

### RAG

RAG finds your app's own text for the model to answer from. Your app creates the chunks from its documents; the module embeds them, with EmbeddingGemma 2, a 0.31 GB model run by llama.cpp, or any OpenAI-compatible API, and keeps them in Qdrant, which also weighs their words for exact matches. **Its page,** Documents, answers from the stored chunks, with each answer's sources under it, numbered, the ones it cites marked. [Its page](docs/modules/rag.md) shows how to produce your chunks, and lists the models and providers.

| Endpoint | What it does |
|---|---|
| `PUT /api/rag/chunks` | Stores your app's chunks, each replacing any stored under its id |
| `GET /api/rag/sources`, `DELETE /api/rag/sources/{source}` | Lists what's stored, or deletes a document's chunks |
| `POST /api/rag/search` | Finds the chunks that best match a question, by meaning and by words |
| `POST /api/rag/ask`, `…/stream` | Answers from the best chunks, citing them as [1]; the stream sends them first |

| Setting | Default | What it sets |
|---|---|---|
| `RAG_ENABLED` | `1` | `0` turns the RAG module off, with its local Qdrant and embedding server |
| `RAG_PROVIDER` | `qdrant` | Where the chunks are kept and embedded: `qdrant`, or `fake` |
| `RAG_LOCAL_QDRANT` | `RAG_ENABLED`'s | `0` leaves the local Qdrant out |
| `RAG_QDRANT_PORT` | `6333` | The local Qdrant's port, with its dashboard |
| `RAG_QDRANT_URL` | `http://qdrant:6333` | The Qdrant to use |
| `RAG_QDRANT_API_KEY` | (none) | Its key |
| `RAG_LOCAL_EMBEDDING` | `RAG_ENABLED`'s | `0` leaves the local embedding server out |
| `RAG_GPU` | `LLM_GPU`'s | The local embedding server's variant |
| `RAG_HF_MODEL` | `ggml-org/embeddinggemma-2-GGUF:Q8_0` | The local embedding model, from Hugging Face |
| `RAG_CONTEXT_SIZE` | `1024` | The longest chunk it embeds, in tokens |
| `RAG_EMBEDDING_PORT` | `8082` | The local embedding server's port |
| `RAG_EMBEDDING_BASE_URL` | `http://embedding:8080/v1` | The OpenAI-compatible embeddings API to use |
| `RAG_EMBEDDING_API_KEY` | (none) | Its key |
| `RAG_EMBEDDING_MODEL` | `local` | The embedding model's name there |
| `RAG_QUERY_FORMAT`, `RAG_DOCUMENT_FORMAT` | EmbeddingGemma 2's | How a question and a chunk are written before they're embedded |
| `RAG_TIMEOUT_SECONDS` | `60` | How long to wait for the embeddings and for Qdrant |
| `RAG_COLLECTION` | `chunks` | The Qdrant collection the chunks are kept in |
| `RAG_BM25_LANGUAGE` | (Qdrant's, English) | BM25's language, for its stop words and stems |
| `RAG_BM25_AVG_LEN` | (Qdrant's, 256) | The chunks' average length in words, for BM25 |
| `RAG_MIN_SIMILARITY` | (off) | The similarity below which a question isn't answered from the chunks |

```
docker compose run --rm rag-demo
docker compose run --rm rag-samples
```

The second stores a fictional shop's help pages, to ask on the Documents page.

## Licence

MIT No Attribution ([LICENSE](LICENSE)): use the template, change it, and sell what you make from it, with no credit asked and no warranty given. The models it downloads have licences of their own, which [docs/models.md](docs/models.md) and each module's page list.
