---
name: start-app
description: Start a new app from this template. Interview the owner about the app, then write its product spec, its first requirements and plan, and its name. Use when spec/product.md still begins with the "Blank template" note, or when the owner asks to start the app.
---

# Start the app

The app starts from a working template: an LLM, a backend, PostgreSQL and a web UI, already tested. This skill writes what's the app's own, its spec, so the work can follow the method in `AGENTS.md`. Write no code here.

1. **Check that the app hasn't started.** If `spec/product.md` no longer begins with the "Blank template" note, say so and stop; the `next-step` skill takes it from there.
2. **Read what's already there:** `AGENTS.md`, `docs/foundations.md`, and the blank `spec/product.md`, `spec/requirements.md` and `spec/plan.md`. The app inherits the foundations; don't ask the owner about them.
3. **Interview the owner, one section of `spec/product.md` at a time,** in this order: the problem, who it's for, what it is, the outcomes, the scope (version 1, next, later), the non-goals, the constraints.
   - Ask a short question, and wait for the answer. Never invent one.
   - If the owner is unsure, offer two or three concrete options to choose from.
   - Say back what you understood before moving on.
   - For the scope, start from what the template already gives: a chat with stored conversations, any model, a web UI. Ask what the app adds, and which modules it may need later, such as RAG, a knowledge graph, a decision model, agent tooling or image models.
4. **Write `spec/product.md`** from the answers: replace the note and every placeholder, keep the headings, and use the owner's words. Show it, and change it until the owner agrees.
5. **Write the app's requirements** in `spec/requirements.md`, under "The app's own", numbered from R15: one row per requirement in the product spec. Where how it's met or verified isn't known yet, say that it's to be planned.
6. **Write the first plan** in `spec/plan.md`:
   - Phase 0 is the spec. Tick 0.1, since it's written; 0.2 is the owner's review.
   - Then a phase towards version 1, in three to six small steps. Each step is one coherent increment, and names the decisions it will need.
7. **Name the app:**
   - set `APP_NAME` in `.env.example`, and in `.env` if there is one;
   - give `README.md` the app's name as its title, and a first paragraph saying what the app is;
   - keep the rest of the README, which tells how to run it.
8. **Commit,** in a few small commits: the spec, the requirements and plan, the name. Then explain what was written, and offer to prepare the plan's first step with the `next-step` skill.
