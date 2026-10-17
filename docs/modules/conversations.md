# The conversations module

Conversations keeps each user's conversations in PostgreSQL. A question carries only itself: the backend adds the stored history before asking the LLM, and stores the question and the answer together once the answer is complete. The module brings the database with it, and its migrations. Why it's built this way is in [the foundations](../foundations.md#conversations).

**Its page,** Chat in the web UI's sidebar, stores each conversation, and lists them under the day of their last answer. It replaces chat's page, which forgets, when both modules are on.

## Try it

With the stack up (`docker compose up -d --wait`):

```
docker compose run --rm conversations-demo
```

The demo starts a conversation, asks in it twice, once whole and once streamed, so the second question is answered with the first in its history; then reads it back, finds it in the user's list, and deletes it. It prints each call, so you can copy them into any language. `CHAT_DEMO_PARAMETERS` adds generation parameters to each question.

## The calls

Every call names its user in `X-User-Id`, a UUID; a user sees only their own conversations, and another user's answers 404 ([users](../foundations.md#users)).

| Endpoint | What it does |
|---|---|
| `GET`, `POST /api/conversations` | Lists the user's conversations, or starts one |
| `GET`, `DELETE /api/conversations/{id}` | Opens a conversation with its messages, or deletes it |
| `POST /api/conversations/{id}/messages`, `…/stream` | Asks in a conversation, whole or as server-sent events; the stream ends with `done`, which carries the stored question's and answer's ids |

## The database

The `postgres` service keeps the data in its own volume, and publishes it on `127.0.0.1:5433` for your own tools; `POSTGRES_PASSWORD` is set when the volume is first created. The `migrate-db` job brings the tables up to date at every start, and the backend waits for it.

- **A database elsewhere:** set `CONVERSATIONS_LOCAL_DATABASE=0`, and `DATABASE_URL` to it, such as `postgresql+asyncpg://user:password@host:5432/app`. The job migrates it at every start, and the backend uses it. On this machine but outside Docker, its host is `host.docker.internal`.
- **After a model changes,** with the stack up, write its migration:

  ```
  docker compose run --rm backend-checks alembic revision --autogenerate -m "what changed"
  ```

  The migrations are in `backend/app/modules/conversations/migrations/`.

## Turn it off, or remove it

- **Off:** `CONVERSATIONS_ENABLED=0` removes its endpoints and its readiness check, and leaves out the migration job and PostgreSQL. Written `0` or `1`: Compose reads it as the job's count too.
- **Removed:** as [the recipe](README.md#remove-a-module) says, and also:
  - in `compose.yaml`, the backend's `depends_on: migrate-db`, and the checks' mount of the migrations' `versions` folder;
  - in `AGENTS.md`, its migration command;
  - in `backend/pyproject.toml`, `[tool.alembic]`, and, if nothing else uses them, the SQLAlchemy, asyncpg and Alembic dependencies, and aiosqlite among the dev ones.

  The database's volume stays until `docker compose down -v`.
