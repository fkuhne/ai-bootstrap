# Plan

The work, as small steps in order. Each step names the decision records it depends on or will create; see the [decision index](decisions/README.md). Each step ends in a few small commits.

**How we work through it**
- One step at a time. Before a step with design choices, the agent lays out the options, the evidence and a recommendation; the owner picks.
- A new decision gets its record first, in its own commit. A Proposed record becomes Accepted in the commit that implements it.
- Guesses go into the matching record's "Assumptions to verify", ticked with evidence once checked.
- Tick the step here in the commit that finishes it.

**Where the app starts.** The template already runs: the LLM, the backend, PostgreSQL and the web UI, with their tests and CI. What they're made of, and why, is in [`docs/foundations.md`](../docs/foundations.md).

## Phase 0: The spec

- [ ] 0.1 The product spec, the app's requirements and this plan
- [ ] 0.2 The owner reviews the spec

## Phase 1: <The first thing the app does>

<!-- Small steps, each a coherent increment that ends in a few commits. -->
- [ ] 1.1 …
