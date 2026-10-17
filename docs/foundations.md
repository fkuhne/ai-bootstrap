# Foundations

What this template is made of, and why: each piece, the choice behind it, and the main alternatives it was chosen over. The code cites these sections where a piece is built. When your app changes one of them, record the change in `spec/decisions/` and update the section here.

**The core,** what every app has:
- [The method](#the-method)
- [A template to start from](#a-template-to-start-from)
- [The stack](#the-stack)
- [The local LLM server](#the-local-llm-server)
- [Models elsewhere](#models-elsewhere)
- [Every parameter and input](#every-parameter-and-input)
- [The LLM port](#the-llm-port)
- [Errors](#errors)
- [The backend's layout and gates](#the-backends-layout-and-gates)
- [Users](#users)
- [The web UI](#the-web-ui)
- [The chat view](#the-chat-view)
- [Reasoning](#reasoning)
- [The check and the demo](#the-check-and-the-demo)
- [CI](#ci)
- [Instructions for agents](#instructions-for-agents)

**The modules,** which an app includes or leaves out:
- [Modules](#modules)
- [Chat, whole or streamed](#chat-whole-or-streamed)
- [Conversations](#conversations)
- [The decision model](#the-decision-model)
- [RAG](#rag)

## The method

Work from a written spec, in small steps, with a record for every decision.

- **`spec/product.md`:** the problem, the users, the scope and the non-goals. It's the source of truth.
- **`spec/requirements.md`:** each requirement, how it's met, and how it's checked.
- **`spec/plan.md`:** phases of small steps, each ticked in the commit that finishes it.
- **`spec/decisions/`:** one numbered record per decision, from `decision-template.md`, with an index.
- **`docs/`:** pages that explain the result to readers, such as this one.

Before a step with design choices, the agent lays out the options, the evidence and a recommendation, and you pick. Guesses go under "Assumptions to verify" and are ticked once checked.

Why: choices made only in a conversation are lost with it. Tools such as Spec Kit and OpenSpec add a program to install and their own structure for each change. Plain Markdown works in every agent, with nothing to install.

## A template to start from

A GitHub template repository: a complete app that CI tests as it is. Start with "Use this template" or a clone, set `.env`, and describe your app in `spec/product.md`. Delete a module you don't need, by [its recipe](modules/README.md#remove-a-module).

Why: Copier and Cookiecutter would turn the files into Jinja templates, so the repository wouldn't run, or pass CI, as it is. A generator program would be one more tool to keep. A library would hide the code you most need to read and change.

## The stack

| Piece | Choice | Why |
|---|---|---|
| Running it | Docker Compose, health checks, one-shot jobs; ports on `127.0.0.1` only | One command on every system |
| Backend | Async FastAPI on uvicorn, Python with uv, organised by domain with ports and adapters | Every outside service behind a port, so tests swap in fakes |
| LLM access | The OpenAI SDK against any OpenAI-compatible API; no LLM framework | Local and cloud models are configuration, not code; an app can add a framework inside an adapter |
| Local LLM | llama.cpp's `llama-server`, pinned to one build | The same model files and settings on CPU, NVIDIA and Vulkan |
| Database | PostgreSQL, SQLAlchemy 2 async and Alembic; SQLite in memory for unit tests | Portable models, migrations checked on PostgreSQL |
| Web UI | React, TypeScript strict and Vite; CSS Modules; served by nginx from one origin | No CORS, a small image, typed end to end |
| API types | Generated from the backend's committed OpenAPI schema | Frontend and backend can't drift apart |
| CI | GitHub Actions running the same commands a user types | It checks what users run |

Every image and dependency is pinned to an exact version.

Why not FastAPI's full-stack template: it has no LLM layer and no streaming, and carries login, e-mail and a reverse proxy most AI prototypes don't need. Why not a TypeScript full stack: most AI libraries, such as embeddings, evaluation and document parsing, are Python first.

## The local LLM server

llama.cpp's `llama-server`, pinned to one build, in the `llm` service.

- **`LLM_GPU`** picks its variant: `cpu` (the default), `nvidia` or `vulkan`. The CPU variant is the one CI runs; the other two haven't been run on a GPU yet. Each file in `compose/` holds only its variant's image and GPU access, and `compose.yaml` holds the rest.
- **`LLM_HF_MODEL`** names a Hugging Face GGUF repository and quantization. The server downloads it on the first start, with its image and audio component, into a volume, and reuses it after. [models.md](models.md) suggests five.
- **`LLM_CONTEXT_SIZE` and `LLM_PORT`** reach the server as its own `LLAMA_ARG_*` variables.
- **The server's own chat page** is published on `127.0.0.1`, beside its API.
- **Only pages served from this machine may call it from a browser** (`LLAMA_ARG_CORS_ORIGINS: localhost`, on the decision server too). llama.cpp allows every origin by default, so any website open in the browser could use the model. The backend calls it from inside Docker, where CORS doesn't apply.

Why one setting: Compose can't detect a GPU, and a container can't see one it wasn't given. Detection would need a launcher script, which differs per shell, or access to Docker's socket. Switching override files is easy to get wrong, and their path separator differs on Windows. ROCm for AMD is a much larger download than Vulkan, which also covers Intel GPUs.

## Models elsewhere

Any OpenAI-compatible API is configuration: `LLM_BASE_URL`, `LLM_API_KEY` and `LLM_MODEL`. [llms.md](llms.md) lists Ollama Cloud, OpenAI, Anthropic, Google Gemini, OpenRouter, and llama.cpp run outside Docker.

- **`LLM_LOCAL_SERVER=0`** leaves the local server out, so nothing is downloaded and no memory is used. Compose reads it as the `llm` service's `scale`.
- **`host.docker.internal`** reaches this machine from the containers on Linux too, so llama.cpp run natively, with Metal on a Mac or Vulkan on Windows, can be used.
- **The LLM check** reaches whatever the backend is set to, with its key, and sends no generation parameters, so it runs on any provider.
- **Readiness counts a 400 as ready:** the model answered, and refused only the probe's one-token limit, as some providers' newer models do.

## Every parameter and input

The template passes through everything the model accepts, and an app narrows it if it wants to.

- **Parameters:** any generation parameter passes through per request, as given, such as `temperature`, `seed`, `reasoning_effort`, or one only a single provider knows. The provider decides what it accepts: Ollama ignores a parameter it doesn't know, and a provider that refuses one says which in its error. The backend adds none of its own.
- **Server-wide settings** that llama.cpp takes only at start, such as the context size, are `.env` settings.
- **Images, audio and video** travel as content parts (`image_url`, `input_audio`, `input_video`) through the API, the database and the web UI. The web UI offers attachments only for what the model accepts.

Why: each app needs a different set of parameters, and a fixed subset would stand in its way. Leaving out the image and audio component would save memory, but take away something the model can do.

## The LLM port

One port, `LLMClient`, whose implementations are interchangeable:

- **Methods:** `complete`, `stream`, `is_ready`, `model_info` and `aclose`. Failures raise the core's errors ([errors](#errors)), never the SDK's.
- **Messages:** a role, and text or typed parts in the shape of OpenAI's API, validated and documented in the API's schema.
- **Answers:** a whole answer with its reasoning, model, finish reason and token usage; or a stream of reasoning and answer pieces, then an end with the same details. Reasoning is read from `reasoning_content` or `reasoning`, whichever the server uses.
- **`OpenAICompatibleClient`** retries a connection error, a 429 or a 5xx, waiting longer each time, but never a timeout: the model may still be working, and a retry would start the same work again. Closing a stream stops the generation. An error carries the provider's own reason.
- **Readiness** is a one-token completion with a 5-second timeout, because a server can list a model before it can answer.
- **The model's inputs** come from the server's model list (`architecture.input_modalities`, as llama.cpp and OpenRouter report it). `LLM_INPUTS` says them for providers that don't. `GET /api/llm/model` tells the model and its inputs, for any page that talks to it, whichever modules are on.
- **`FakeLLMClient`** answers "Fake answer to: …" without a model, and takes every input. `LLM_PROVIDER=fake` selects it, for tests and CI.

Why not a framework such as LangChain or LiteLLM: a layer over what the OpenAI-compatible API already gives, which changes often. Why not the SDK's own retries: they retry timeouts too.

## Errors

One set of errors, in `backend/app/core/errors.py`, which every domain raises, each answered with its status and its message as the detail:

| Error | Status | When |
|---|---|---|
| `NotFoundError` | 404 | What the request names doesn't exist for this user |
| `ConflictError` | 409 | The request conflicts with what's stored |
| `ServiceError` | 502 | A service the app calls refused the request, or failed: the message gives its reason |
| `ServiceRateLimitedError` | 429 | The service is limiting how often it's called |
| `ServiceUnavailableError` | 503 | The service can't be reached, or is down, overloaded or still loading |
| `ServiceTimeoutError` | 504 | The service didn't answer in time |

- **One handler,** in the core, answers them, and logs a 5xx's cause, which the answer leaves out.
- **A stream** that an error stops ends with an `error` event carrying the status the same request answers unstreamed: `error_event` in the same file.
- **A service's failed answer** becomes one of them by one rule, in `backend/app/core/services.py`: 429 is rate-limited; 502, 503, 504 and 529 are a server that's down, overloaded or loading its model; any other status is a refusal, with the reason the service gave, such as llama.cpp's 500 for a text longer than its batch. The OpenAI SDK's errors are translated once, for the LLM and the embeddings, in `backend/app/llm/openai_errors.py`.
- **Readiness probes** wait 5 s, and run at once, so a service that hangs holds the answer only that long.
- **A domain subclasses an error** only where a caller tells its own apart, as conversations' `ConversationNotFoundError`, a `NotFoundError`.

Why one set in the core: the status of each kind of failure is decided once, and a module adds none of its own plumbing. Why a server's 500 is a refusal: llama.cpp answers it for a text too long for its batch, which waiting won't fix.

## The backend's layout and gates

- **`backend/app/`** holds the core's domains, `llm/`, `users/` and `health/`; `core/`, for what every domain shares: settings, [errors](#errors), logging and the `Module` contract; the modules, each in `modules/<name>/`; and `main.py`, which wires them together. Import-linter contracts keep the layers, no domain importing one above it, and keep the modules from importing each other.
- **Settings:** one pydantic-settings class per domain, with its own prefix (`APP_`, `LLM_`, `RAG_`) and its defaults in the code, read once through `settings_of`, in `app/core/config.py`. A module names its classes in its `Module`; the tests start each from the defaults by its prefix. Compose passes a setting through only when it's set, so each default lives in one place. An empty value counts as unset.
- **Logging:** the standard `logging` module, in one format for every line, with local times set by `TZ`.
- **The image** builds the virtual environment with uv and a lockfile, and runs as a user that isn't root.
- **Gates:** ruff, mypy strict, the import contract, and pytest with at least 90% branch coverage. A warning fails its test. `docker compose run --rm backend-checks` runs them on a read-only mount of the source, the same on every system. Live tests, against running services, are marked `integration` and left out by default.

Why one settings class per domain: a module can then be deleted with its settings. Why the gates in Docker: tools installed on each machine differ.

## Users

There's no login. The browser makes a random UUID once, keeps it, and sends it as `X-User-Id`. One FastAPI dependency, `current_user` in `app/users/`, reads it, and every domain takes the user from there.

An app that adds login replaces that one function. An anonymous id isn't security: it keeps browsers apart, and gives the code the shape real login needs.

## The web UI

React and Vite in `frontend/`, laid out and colored as llama.cpp's own web UI: neutral grays, light or dark as the system is, Lucide icons, and a sidebar that becomes a drawer below 768 px.

- **A shell, and the modules' pages.** The shell is the frame and the sidebar. Each module with a page gives it as a `UiModule`, in `frontend/src/modules/<name>/`, listed in `frontend/src/modules/index.ts`:
  - its name, as the backend calls it; its title and icon in the sidebar; its path; its page;
  - if it needs them: its sidebar content, a provider for state its page and sidebar share, and the modules whose page it replaces.

  The shell asks `GET /api/modules`, again every 3 s while it can't, and shows each module that's on and not replaced by another: an entry in the sidebar when there's more than one, the open one's sidebar content, its pages under `/<path>/`. `/` goes to the first.
- **The core's parts,** which pages share:
  - `src/api/`: requests and their errors, server-sent events and a streamed POST, which passes the events a module names beside the core's, the user's id, readiness, the model and the modules;
  - `src/llm/`: the LLM's view, for any page that talks to the model: the message form, the messages, the reasoning box, Markdown, media, a streamed answer's states, the line saying how an answer was made, and `ChatView`, the page they make;
  - `src/health/`: readiness. Each page names the checks it needs, with words for its modules' own; the backend's being unreachable always shows.
- **nginx** serves the build and forwards `/api` to the backend, from one origin, at `127.0.0.1:${FRONTEND_PORT:-3000}`. Streams pass through unbuffered. The pages get a strict content security policy.
- **It starts first,** depending on nothing, and names what the open page needs and isn't ready, checked every 3 s.
- **`APP_NAME`** names the page as well as the API.
- **The API's types** are generated: `docker compose run --rm backend-checks python -m app.openapi` writes the schema, then `docker compose run --rm frontend-checks npm run api:types` the types. Tests fail while either is out of date. The core's own models, such as the LLM's message, are in the schema whichever modules remain, so the core's view is typed by them.
- **Gates:** `docker compose run --rm frontend-checks` runs oxlint, Prettier, TypeScript, the types' check and Vitest. Its image copies the source at every run, so packages installed on the host never reach it.

Why plain CSS Modules on a few color tokens, not Tailwind: the look comes from the tokens, with no build plugin. Why a list of its own, not titles and paths from the backend: the web UI decides how it shows a module; the backend says only which are on. Hot reload is `npm --prefix frontend run dev` on a machine with Node 24.

## The chat view

`ChatView`, in `src/llm/`, which chat's, conversations' and RAG's pages use:
- **A new conversation,** on conversations' page, is created by its first message; the address then moves to `/conversations/<id>`, and the answer keeps streaming. Chat's page keeps its conversation in the browser instead, until a reload or "New chat".
- **The answer streams** after "Processing…": the reasoning in its box, then the answer as Markdown as it arrives. Raw HTML stays text. Once complete, it joins the conversation: on conversations' page as the backend stored it, with the model, its tokens and its time; on chat's, with the model and its tokens.
- **Stop:** the round button aborts the request, so the backend stops the model. Conversations stores nothing, and chat leaves the answer out of the conversation.
- **Failures** are explained in plain words by their status, with the backend's message as a detail.
- **Below an answer,** a module may show its own, as RAG's sources: a message's `extra`, and `answerExtra` for the answer streaming.
- **Attachments:** a paperclip appears when the model takes images, audio or video, as `GET /api/llm/model` reports. Files go as base64 content parts.

Why not always offer attachments: a text-only model would refuse them only after the upload. Why no tokens-per-second figure: reasoning counts among the tokens, and cloud providers send answers in bursts, so it would mislead.

## Reasoning

- **A dropdown beside the model's name** sets how much the model reasons: Auto sends nothing, so the model decides; None, Low, Medium and Max send `reasoning_effort` as `none`, `low`, `medium` and `high`, the highest value every provider documents. The choice is kept in the browser.
- **The reasoning shows in a box** above the answer: open while it's written, following its newest line, and folded once the answer starts.

Why `reasoning_effort`: OpenAI, Ollama and llama.cpp's server all take it. llama.cpp's own web UI sends fields only llama.cpp reads.

## The check and the demo

- **`docker compose run --rm llm-check`**, the core's, asks the LLM a question in each input it accepts, and prints the model, the answer and the speed.
- **Each module's demo,** such as `docker compose run --rm decision-demo`, calls the backend as an app would, and prints each request's body, so the calls can be copied into any language; each module's page says what its demo asks. Each checks only the readiness it needs, so it passes while another module is down. They share the core's `scripts/demo.py`, which calls the backend, prints each call and shows an LLM's answer.

They're Python scripts using only the standard library, run in a pinned Python image. They check the calls, never what the model says, which depends on the model.

## CI

`.github/workflows/ci.yml` runs only commands a user types:
1. the gates, backend and web UI;
2. the stack with the fake model: the web UI starting before anything else, readiness through nginx, and the live tests;
3. the stack with the default local model on CPU, on pushes to `main` and on demand: the LLM check and the live tests.

Each module's own workflow, `.github/workflows/<name>.yml`, starts only the services it needs and runs its demo, through the backend and through nginx; conversations' also checks the migrations against the models on PostgreSQL, and RAG's checks what its sample questions find.

A small action points Docker at Google's mirror of Docker Hub, whose anonymous pulls are rate-limited on shared runners. Actions are pinned to a commit.

Why not steps that install Python or Node on the runner: CI would pass commands no user types.

## Instructions for agents

`AGENTS.md` is the single source of instructions: short, with detail in `spec/` and `docs/`. Codex, Cursor, GitHub Copilot and Claude Code read it. `CLAUDE.md` and `GEMINI.md` each hold one line, `@AGENTS.md`, for older Claude Code versions and for Gemini CLI. The method's routines are Agent Skills, an open format most coding agents read:
- `start-app` interviews the owner and writes the app's spec;
- `next-step` lays out the plan's next step for the owner to pick;
- `decide` writes a decision record;
- `add-module` agrees a new module with the owner, then builds it by [the recipe](modules/README.md).

They live in `.agents/skills/`, which Codex, GitHub Copilot, Cursor and Gemini CLI read. Claude Code reads `.claude/skills/`, where a one-line copy of each points to them; symbolic links would break on Windows checkouts. Everything a skill does can also be asked of any agent in plain words.

## Modules

The core is what every app has, or what its modules share: the backend's skeleton, the LLM port, users, the web UI's shell, Compose, CI and the method. Everything else is a **module**, which an app includes or leaves out, in any order: chat, conversations, a decision model and RAG on Qdrant so far; a knowledge graph, agent tooling and image models may follow. The web UI consumes the modules; it doesn't decide what the core holds.

A module lives in places of its own:
- `backend/app/modules/<name>/`: its settings and its routes, and, when it reaches a service of its own, a port with an adapter and a fake; its tests in `backend/tests/unit/modules/<name>/`, and its live tests, if it has any, in `backend/tests/integration/modules/<name>/`;
- `frontend/src/modules/<name>/`, if it has a page: its page, its calls and types, and its tests, listed in `frontend/src/modules/index.ts`;
- `compose/modules/<name>.yaml`, for its services and its demo, which `compose.yaml` pulls in with one `include:` line;
- `scripts/modules/<name>/`, for its demo, which calls the backend as an app would and checks each answer;
- `.github/workflows/<name>.yml`, its own CI;
- `docs/modules/<name>.md`, its page.

It plugs in through one list:
- **`MODULES`,** in `backend/app/modules/__init__.py`, holds one `Module` object per module: its routes and its settings, and what it may have, its clients' start and close, its readiness check and the models of the events it streams. Its errors are the core's ([errors](#errors)).
- **The core wires each one its settings turn on:** its routes under `/api`, its clients, its line in `/api/health/ready`, checked at once with the others, its events in the API's schema. Its switch, `<NAME>_ENABLED`, such as `RAG_ENABLED=0`, turns it off, and Compose reads it as the count of the module's own services, which follow it unless their own setting says otherwise. Every module's settings derive from the core's `ModuleSettings`, which holds it.
- **`GET /api/modules`** lists the modules that are on, and the web UI shows the pages of those, from its own list ([the web UI](#the-web-ui)).
- **The API's schema includes every module,** on or off, so the committed schema is the same on every machine.
- **An import contract** keeps modules from importing each other.

**[Adding a module](modules/README.md)** follows a recipe, place by place, with the files its backend holds and what goes in each; the same page says how to remove one. A test in the backend's gates checks that each module in `MODULES` has its places, and that none is left of a module that's gone.

**What's core:** a piece moves to the core when a second module needs it, as the LLM is shared by chat, conversations and RAG; until then it stays in the module that has it, as the database in conversations and the embedder in RAG.

Why a list, not discovery: you can read which modules an app has, and where each is wired. Why a recipe and a check, not a skeleton module to copy: the decision module already shows every part, and a skeleton would be code no app runs. Why not every capability in the core, switched off by settings: every app would carry code it doesn't use, and couldn't delete it.

## Chat, whole or streamed

A module, `CHAT_ENABLED=0` turns it off. It has no service of its own: it asks the core's LLM port. Its page, `/chat`, keeps the conversation in the browser; conversations' page replaces it when both are on.

- **`POST /api/chat`** returns the whole answer; **`POST /api/chat/stream`** sends server-sent events: `reasoning` and `token` pieces, then `done` with the model, the finish reason and the usage. Both are stateless: the caller sends the whole conversation.
- **A failure once the stream has started** ends it with an `error` event, carrying the HTTP status the same request gets without streaming. Closing the stream stops the model.
- **The body** is `{"messages": [...], "parameters": {...}}`. Parameters are an object of their own, so they can't collide with the API's fields.
- **LLM errors** become HTTP 504 (timeout), 503 (unreachable or down), 429 (rate-limited) or 502 (refused, with the provider's reason), as every service's do ([errors](#errors)).

Why not one endpoint with a `stream` flag: the two answers have different shapes. Why not WebSockets: a two-way channel for a one-way stream, and harder for proxies. Why not the provider's raw chunks: each provider's differ, so every client would parse them; the port reads them once.

## Conversations

A module, with the database: `CONVERSATIONS_ENABLED=0` turns off its endpoints, its readiness check, its migration job and PostgreSQL. Readiness reports it as `conversations`. Its page, `/conversations`, stores each conversation and lists them in the sidebar.

- **The store:** a `ConversationStore` port with its SQL adapter. Every operation is scoped to the user; another user's conversation answers 404, as a missing one does. A database failure answers 503.
- **A message** keeps its content as the API took it, media included, an answer's reasoning, and how it was made: the model, the finish reason, the usage and the times. Each message points to the one before it, so a later feature could branch a conversation.
- **Asking in a conversation:** `POST /api/conversations/{id}/messages`, whole or `/stream`, sends the stored history and the new question to the model. The question and the answer are stored together, only once the answer is complete: a failure, or a client that leaves, stores nothing.
- **The first question with text** gives the conversation its title.

Why store a turn only once it's complete: a question stored without its answer would be sent again with every later turn. Why the database goes with conversations: nothing else uses it. A later module that needs one brings it back to the core, shared as the LLM port is.

### The database

The conversations module's, in `compose/modules/conversations.yaml` and `backend/app/modules/conversations/`:
- **PostgreSQL** in the `postgres` service, published on `127.0.0.1:5433`, not 5432, which a PostgreSQL on the host often holds. `CONVERSATIONS_LOCAL_DATABASE=0` leaves it out, for a database elsewhere that `DATABASE_URL` names.
- **The `migrate-db` job** runs Alembic's migrations, in the module's `migrations/`, at every start, then exits. The backend waits for it through an optional dependency, so it starts at once when the module is off. Write a migration with `docker compose run --rm backend-checks alembic revision --autogenerate -m "…"`.
- **One backend image** serves the API and the job, both extending `compose/backend.yaml`. It's named after the Compose project, so two apps on one machine don't share it.
- **Tests:** unit tests run on SQLite in memory; the module's workflow checks the migrations against PostgreSQL itself.

Why a job, not migrations at the backend's start: replicas would race to migrate, and a failed migration would look like a crashed API.

### The conversation list

Conversations' sidebar content starts with "New chat", then the user's conversations under Today, Yesterday, Previous 7 days and Older, newest first, the open one shaded. A conversation is listed once its first answer is stored. Deleting asks in the row itself, with the focus on Cancel. A list that fails to load tries again every 3 s.

## The decision model

A module that answers typed questions about a text, or an object, with probabilities rather than generated text: for an agent's routing, and for classification. `POST /api/decide` takes the System One format: a `state`, and `questions` by name, each `noul` (yes or no), `choice` (one of named options) or `score` (a level on a scale), each answered with probabilities. [Its page](modules/decision.md) gives the format in full, the models and the cloud providers.

- **A `DecisionModel` port,** with one adapter for any System One endpoint, set by `DECISION_BASE_URL`, `DECISION_API_KEY` and `DECISION_MODEL`: llama.cpp's own server with a native decision model, such as Laya; TypeSafe; or OpenRouter. `DECISION_PROVIDER` is `systemone`, the default, or `fake`. Readiness asks one small question.
- **The local service,** `decision`, in `compose/modules/decision.yaml`: llama.cpp's pinned server, the LLM's own image, on the LLM's variant unless `DECISION_GPU` says otherwise, with Laya by default. `DECISION_LOCAL_SERVER=0` leaves it out, when the model is in the cloud.
- **The batch** is as large as the context, `DECISION_CONTEXT_SIZE`: a decision model reads each prompt in one batch, and llama.cpp's default of 512 tokens refused a 700-word text.
- **Its page,** `/decision`, opens with an example of each type of question, edits them in place, and shows the answers as bars.

`DECISION_ENABLED=0` turns it off, with its local service.

Why the format as it is, not question types of our own: three providers already share it, so a translation layer would add code without adding reach.

## RAG

A module that finds an app's own text for the model to answer from. The app creates its chunks from its own documents, and stores them; the module embeds them, keeps them in Qdrant, and searches them two ways, by meaning and by exact words, fused into one list. [Its page](modules/rag.md) shows how to produce and store chunks, and lists the models, with each one's formats, and providers elsewhere.

- **Its services,** in `compose/modules/rag.yaml`: `qdrant`, Qdrant's pinned, unprivileged image, which also computes each chunk's BM25 weights from its text; and `embedding`, llama.cpp's pinned server in embedding mode, with EmbeddingGemma 2 by default, on the LLM's variant unless `RAG_GPU` says otherwise. `RAG_LOCAL_QDRANT=0` and `RAG_LOCAL_EMBEDDING=0` leave them out, for services elsewhere.
- **The batch** of the embedding server, `RAG_CONTEXT_SIZE`, 1,024 tokens, is the longest text it takes, and bounds its memory: about 1 MB per token on CPU, however many texts a request carries.
- **Two ports:** an `Embedder`, with an adapter for any OpenAI-compatible `/v1/embeddings`, which writes chunks and questions each in the model's own format; and a `ChunkStore`, with an adapter for Qdrant's REST API. `RAG_PROVIDER` is `qdrant`, the default, or `fake`, with a fake of each. Readiness needs both.
- **Its endpoints:** an app stores its chunks with `PUT /api/rag/chunks`, each under a UUID made from the app's own id, so storing it again replaces it, and lists and deletes them by source; `POST /api/rag/search` finds them, fused by rank with Qdrant's RRF, or by meaning or words alone; `POST /api/rag/ask`, and `/ask/stream`, give the model the best chunks, numbered, to answer from and cite as `[1]`. With no chunk found, or none as similar as `RAG_MIN_SIMILARITY`, off by default, the answer is "The documents don't say." and the model isn't asked.
- **One collection,** `RAG_COLLECTION`, made on the first store for the embedding model, whose vector for a fixed probe text it records, since llama.cpp's server answers to any name: a store with another model is refused with 409.
- **Its page,** Documents, answers from the stored chunks, each answer's sources under it; `docker compose run --rm rag-samples` stores a fictional shop's help pages for it, and checks that each sample question finds its chunk.

`RAG_ENABLED=0` turns it off, with its local services.

Why Qdrant computes BM25: the backend then runs no model of its own, and its image stays small. Why embeddings from llama.cpp's server: the same pinned image and GPU variants as the LLM, and any provider with an OpenAI-compatible `/v1/embeddings` takes its place by configuration. Why its REST API rather than Qdrant's client library: a few calls, without the library's gRPC and numpy. Why HTTP for storing rather than a function: nothing outside the module may import it, so an app's ingestion, in any language, calls the endpoint. Why fusion by rank: a similarity and an unbounded BM25 score combine without tuning. Why the refusal on the similarity, not the fused score: a fused score is a rank, and says nothing of how relevant the first hit is. Why the sources under each answer: the `[n]` are the model's writing, and a reader checks them there. Why among the first three, not first: a change of model can swap two close chunks without anything being wrong.
