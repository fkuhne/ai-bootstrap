# AGENTS.md

Instructions for coding agents working in this repository. Keep this file short: detail belongs in `spec/` and `docs/`, read when a step needs it ([foundations](docs/foundations.md#instructions-for-agents)).

## What this is

An AI app built on ai-bootstrap's foundations: a FastAPI backend, a React web UI, PostgreSQL and an LLM reached through any OpenAI-compatible API, run by Docker Compose, plus a spec-driven way of working. What the app is for is in [`spec/product.md`](spec/product.md); what it's made of, and why, is in [`docs/foundations.md`](docs/foundations.md).

## Start the app first

If [`spec/product.md`](spec/product.md) still begins with the "Blank template" note, the app hasn't been started. Before anything else, help the owner start it, with the [`start-app`](.agents/skills/start-app/SKILL.md) skill or by these steps:
1. Ask what the app is for: the problem, who it's for, what it does first, and what it won't do. Fill in `spec/product.md` from the answers, one section at a time, and let the owner review it.
2. Add the app's own requirements to `spec/requirements.md`, after the template's.
3. Write a first plan in `spec/plan.md`: the spec as Phase 0, then small steps.
4. Name the app: set `APP_NAME` in `.env.example`, and in `.env` if there is one, and give `README.md` the app's title and a first paragraph.
5. Commit, then work through the plan as below.

## Read before acting

1. [`spec/product.md`](spec/product.md): what we build and what we don't. It's the source of truth for scope.
2. [`spec/requirements.md`](spec/requirements.md): each requirement, how it's met and how it's verified.
3. [`spec/plan.md`](spec/plan.md): the steps, in order. The next step is the first unticked one.
4. [`spec/decisions/README.md`](spec/decisions/README.md): the decision records that touch the step.

## How we work

- **One plan step at a time.** Before a step with design choices, lay out the options, the evidence and a recommendation, and let the owner pick. Don't decide a whole step alone.
- **Show evidence the owner can see:** real output, real numbers, a check failing before it's trusted. Not just "tests pass".
- **A record for every decision**, from [`spec/decisions/decision-template.md`](spec/decisions/decision-template.md), committed on its own or with the change it justifies. Proposed becomes Accepted in the commit that implements it. A reversed decision gets a new record, and the old one is marked superseded.
- **Guesses go under "Assumptions to verify"**, ticked with evidence once checked.
- **Small commits,** each one coherent increment, none referencing files that only arrive later. Tick the plan step in the commit that finishes it.
- **A change of scope starts in `spec/product.md`.** When the code departs from the plan, update the plan in the same change.
- **After a step,** explain what was built and why, with links to the lines, before moving on.
- **Skills** run these routines: [`next-step`](.agents/skills/next-step/SKILL.md) prepares the plan's next step, [`decide`](.agents/skills/decide/SKILL.md) writes a record, and [`add-module`](.agents/skills/add-module/SKILL.md) adds a module by its recipe. They live in `.agents/skills/`; `.claude/skills/` points Claude Code to them.

## Commands

- `docker compose up -d --wait` starts the stack; `docker compose down` stops it.
- `docker compose run --rm llm-check` asks the LLM a question in each input it accepts.
- Each module's demo, such as `docker compose run --rm chat-demo`, calls the backend as an app would, and checks each call.
- `docker compose run --rm backend-checks` runs the gates: ruff, mypy, import-linter and pytest with coverage for the backend, and ruff and mypy for `scripts/`. CI runs the same commands ([foundations](docs/foundations.md#ci)). After a dependency changes, run `docker compose build backend-checks` first.
- `docker compose run --rm backend-checks pytest -m integration --no-cov` runs the live tests against the configured LLM and PostgreSQL.
- `docker compose run --rm frontend-checks` runs the web UI's gates: oxlint, Prettier, TypeScript, the API types' check and Vitest. `... npm run format` formats `frontend/src/`.
- After an endpoint or an API model changes, `docker compose run --rm backend-checks python -m app.openapi`, then `docker compose run --rm frontend-checks npm run api:types`, regenerate the schema and the web UI's types; commit both ([foundations](docs/foundations.md#the-web-ui)).
- `docker compose run --rm backend-checks alembic revision --autogenerate -m "<change>"`, with the stack up, writes the conversations module's migration after one of its models changes; `... alembic check` tells whether models and migrations agree.

## Conventions

- English everywhere: code, docs, UI text, prompts.
- All configuration comes from environment variables, each with a working default; `.env` is optional. A new setting also gets a line in `.env.example`.
- Every command a user types works unchanged in PowerShell, cmd and POSIX shells: Docker commands, not shell scripts.
- Pin images and dependencies to exact versions.
- Never require a paid or cloud-only service. A cloud LLM is configuration, never a separate code path.
- Ports are published on `127.0.0.1` only.
- Backend code goes in a domain folder under `backend/app/`, with its own settings class; `app/main.py` wires it in ([foundations](docs/foundations.md#the-backends-layout-and-gates)).
- A module's page goes in `frontend/src/modules/<name>/`, as a `UiModule` listed in `frontend/src/modules/index.ts`, with its calls, types, CSS modules and tests beside it. The shell, `src/api/`, `src/llm/` and `src/health/` are the core's. Pages call the API through `request` and the generated types, and style on the tokens in `src/index.css` ([foundations](docs/foundations.md#the-web-ui)).
- A capability an app may not need is a module, built place by place by the recipe in [`docs/modules/README.md`](docs/modules/README.md): its code in `backend/app/modules/<name>/`, listed in `MODULES`, with its switch, `<NAME>_ENABLED`, and a port, an adapter and a fake when it reaches a service of its own. A test among the gates checks that it has all its places ([foundations](docs/foundations.md#modules)).
