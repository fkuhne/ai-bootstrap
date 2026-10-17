# Modules

A module is a capability an app includes or leaves out: it plugs into the core through one list, and comes out by deleting its places ([the foundations](../foundations.md#modules)). These are the template's:

| Module | What it does | Its switch |
|---|---|---|
| [chat](chat.md) | Asks the LLM with the conversation the caller sends, whole or streamed | `CHAT_ENABLED` |
| [conversations](conversations.md) | Keeps each user's conversations in PostgreSQL, and asks in them | `CONVERSATIONS_ENABLED` |
| [decision](decision.md) | Answers typed questions about a text with probabilities | `DECISION_ENABLED` |
| [rag](rag.md) | Answers from your app's own chunks, citing them | `RAG_ENABLED` |

Below: how to add a module, place by place; what belongs in the core rather than in a module; and how to remove one. A test checks that each module has its places.

## Add a module

Follow the decision module: it has every part, a service of its own, reached through a port with an adapter and a fake, a page, a demo and a workflow. Give the module a name of one lowercase word, `<name>`; its settings take the prefix `<NAME>_`. With a coding agent, the `add-module` skill walks through this page with you.

### 1. The backend, in `backend/app/modules/<name>/`

| File | What goes in it |
|---|---|
| `__init__.py` | One line: `from app.modules.<name>.module import MODULE` |
| `config.py` | Its settings class, deriving from the core's `ModuleSettings` with `env_prefix="<NAME>_"`: its switch, `<NAME>_ENABLED`, comes with it. A `provider` setting picks the real adapter or the fake. Each setting has a working default. |
| `router.py` | Its endpoints, under `/api/<path>`, each with the statuses it answers on failure, written with the core's `described` |
| `schemas.py` | The API's own models: what its endpoints take, answer and stream. When the API speaks the port's own format, as decision's does, the port's file holds them. |
| `<thing>.py` | For each service it reaches, a port: a `Protocol` with what the module needs, and `is_ready` and `aclose` |
| `<technology>_<thing>.py` | The port's adapter. A failure becomes one of the core's errors: `timed_out`, `unreachable` and `status_error`, in `app/core/services.py`, decide which; an OpenAI-compatible API's go through `app/llm/openai_errors.py`. Its readiness probe waits `READINESS_TIMEOUT_SECONDS`. |
| `fake_<thing>.py` | The port's fake, which the tests and `<NAME>_PROVIDER=fake` use |
| `factory.py` | Builds the adapter or the fake from the settings |
| `<what it does>.py` | When an endpoint does more than call the port, the service it calls, such as RAG's `index.py` or conversations' `conversation_answerer.py` |
| `exceptions.py` | Only an error a caller tells apart, subclassing one of the core's, in `app/core/errors.py`. Every other failure is one of the core's, which the core's handler answers with its status. |
| `dependencies.py` | FastAPI dependencies that hand the endpoints what `module.py` started |
| `module.py` | Its `Module`: its name, router and settings class, and, when it has them, its `lifespan`, which starts its clients on `app.state` and closes them, its `is_ready`, and the models of the events it streams |

A module without a service of its own, as chat, needs only `__init__.py`, `config.py`, `router.py`, `schemas.py` and `module.py`. A module may use the core, `app.core`, `app.llm` and `app.users`, but no other module: an import contract fails if it does.

Then:
- **Its line in `MODULES`,** in `backend/app/modules/__init__.py`.
- **Its tests,** in `backend/tests/unit/modules/<name>/`: its endpoints through the app on the fake (`create_app(modules=[MODULE])`), its adapter on a mock transport, its fake. Its live tests, against the real service, go in `backend/tests/integration/modules/<name>/`, marked `integration`.
- **The API's schema and the web UI's types,** regenerated after an endpoint or a model changes, as `AGENTS.md`'s commands say.

### 2. Its services, in `compose/modules/<name>.yaml`

- **Each service** pinned to an exact version, with a health check, its ports on `127.0.0.1`, and `scale: ${<NAME>_LOCAL_<SERVICE>:-${<NAME>_ENABLED:-1}}`: the module's switch takes it along, and a setting of its own leaves it out when it runs elsewhere.
- **Its demo,** a service in the `tools` profile that runs its script.
- **In `compose.yaml`:** its line under `include:`, and each of its settings, by name, among the backend's (`x-backend-environment`), so Compose passes each one through when it's set.

### 3. Its settings, in `.env.example`

A section, `# --- The <name> module ---`, with a line for each setting: its default, and in a comment what it does. A service's own switch stays commented out, so that it follows the module's.

### 4. Its demo, in `scripts/modules/<name>/`

A script that calls the backend as an app would, through the core's `scripts/demo.py`, prints each call so it can be copied into any language, and checks each answer. Standard library only.

### 5. Its CI, in `.github/workflows/<name>.yml`

It starts only the services the module needs, waits for readiness, runs the module's live tests if it has any, and runs its demo through the backend and through the web UI's origin. Start from decision's.

### 6. Its page in the web UI, in `frontend/src/modules/<name>/`, if it has one

A `UiModule`, as `frontend/src/uiModule.ts` describes it: its name as the backend gives it, its title and icon in the sidebar, its path, its page, and, if it needs them, its sidebar content and a provider. List it in `frontend/src/modules/index.ts`. It calls the API through `src/api/` and its generated types, and uses the core's `src/llm/` and `src/health/` where they fit.

### 7. Its docs

- **Its page, `docs/modules/<name>.md`:** what it does, how to try it, its calls, its models or providers, and how to turn it off or remove it.
- **A row in the table above,** and its section in the README, under Modules: what it does, its page, its endpoints, its settings and its demo.

### The check

`docker compose run --rm backend-checks`, the backend's gates, runs `tests/unit/test_module_places.py`. It fails naming each place a module in `MODULES` lacks: its Compose file and its `include:` line, its demo's folder, its workflow, its page, its section in `.env.example`, and each of its settings passed to the backend and given a line in `.env.example`. It also names what's left of a module that's gone.

## What's core, and what's a module

A piece moves to the core when a second module needs it, as the LLM is shared by chat, conversations and RAG. Until then it stays in the module that has it: the database in conversations, the embedder in RAG. To move one, its code goes to a domain of the core, `backend/app/<domain>/`, its services to `compose.yaml`, and the modules that use it import it from there.

## Remove a module

1. **Delete its places:** `backend/app/modules/<name>/` and its tests, `frontend/src/modules/<name>/`, `compose/modules/<name>.yaml`, `scripts/modules/<name>/`, `.github/workflows/<name>.yml` and `docs/modules/<name>.md`.
2. **Delete its lines:** in `MODULES`, and in `frontend/src/modules/index.ts`; in `compose.yaml`, under `include:` and among the backend's settings; its section in `.env.example`; its row above, and its section in the README; and any other line its page lists.
3. **Regenerate** the API's schema and the web UI's types.
4. **Run the gates:** the check names anything left behind.
