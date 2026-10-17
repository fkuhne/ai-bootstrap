# Requirements

Each row comes from [`product.md`](product.md) and says how it will be met and how we'll know. A row isn't traded away for convenience. If one has to change, change `product.md` first.

"How it's met" names the plan or the decision while the row is still to build. Once built, it names the code.

## From the template

What the app inherits, already met and checked by the template's tests and CI. Delete a row only with what it covers, such as the web UI.

| # | Requirement | How it's met | How it's verified |
|---|---|---|---|
| R1 | One command starts the whole stack on Windows, Linux and macOS | `docker compose up -d --wait`; health checks and one-shot jobs order the start ([foundations](../docs/foundations.md#the-stack)) | CI starts the stack on Linux; Windows and macOS are checked before each release |
| R2 | No paid or cloud-only service is needed | A local LLM by default, or the fake; a cloud provider is configuration ([foundations](../docs/foundations.md#models-elsewhere)) | CI runs with no API key |
| R3 | Any OpenAI-compatible LLM, chosen in `.env` alone | One LLM port, an adapter on the OpenAI SDK; `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY` ([foundations](../docs/foundations.md#the-llm-port)) | Unit tests on the adapter; the LLM check against the local server in CI |
| R4 | The stack runs without any model, for development and tests | `LLM_PROVIDER=fake`, a deterministic stub | Unit tests and a CI job use it |
| R5 | A web UI that streams answers and keeps conversations | React served by nginx; server-sent events; a conversation sidebar; the chat and conversations modules' pages ([foundations](../docs/foundations.md#the-web-ui)) | Frontend tests; the modules' CI runs their demos through nginx |
| R6 | Conversations stored in PostgreSQL, the schema migrated by a job | SQLAlchemy 2 async, Alembic, the `migrate-db` job, in the conversations module ([foundations](../docs/foundations.md#the-database)) | `alembic check` on PostgreSQL in the module's CI; unit tests on SQLite |
| R7 | Backend quality gates | Coverage ≥ 90% on `app/`, mypy strict, ruff, import-linter contracts ([foundations](../docs/foundations.md#the-backends-layout-and-gates)) | CI fails below any gate |
| R8 | Frontend quality gates; API types that can't drift from the backend | oxlint, Prettier, TypeScript strict, Vitest; types generated from the committed OpenAPI schema | CI fails on any gate, or when the types differ from the schema |
| R9 | Every setting has a working default and is documented | pydantic-settings classes; `.env.example` | Each new setting gets its line in `.env.example` |
| R10 | Any coding agent can work in the repo by the method | `AGENTS.md`, read by most agents; `CLAUDE.md` and `GEMINI.md` import it ([foundations](../docs/foundations.md#instructions-for-agents)) | The agents the team uses follow it |
| R11 | A module can be added or removed without editing the core | Each module is a backend domain, a Compose file and, if it has a page, a folder in the web UI, each in its list; `GET /api/modules` says which are on; import-linter contracts keep modules apart ([foundations](../docs/foundations.md#modules)) | Deleting a module's places and its lines, as its page lists them, leaves CI green |
| R12 | Every decision has a record | `spec/decisions/`, from `decision-template.md` ([foundations](../docs/foundations.md#the-method)) | Reviewed at the end of each phase |
| R13 | Every generation parameter the model accepts can be set per request | The LLM port passes standard and provider-specific parameters through ([foundations](../docs/foundations.md#every-parameter-and-input)) | Unit tests on the adapter |
| R14 | Images, audio and video in the user's messages, wherever the model accepts them | The server loads the model's image and audio component; the API, the database and the web UI carry all three ([foundations](../docs/foundations.md#every-parameter-and-input)) | The LLM check sends an image and a sound to a model that takes them; API and frontend tests |

## The app's own

<!-- One row per requirement from product.md, numbered from R15. -->

| # | Requirement | How it's met | How it's verified |
|---|---|---|---|
