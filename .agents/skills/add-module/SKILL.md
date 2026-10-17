---
name: add-module
description: Add a module to the app, a capability it includes or leaves out, such as a model or a service of its own. Agree with the owner what it does and how it's reached, record the choices, then build it place by place by docs/modules/README.md, and run the check that it has every place. Use when the owner asks for a capability an app may not need.
---

# Add a module

1. **Read the recipe,** `docs/modules/README.md`, and the module it names as the example, decision, from `backend/app/modules/decision/` to its page; then `docs/foundations.md#modules`, and the foundations' sections of whatever the module will use, such as the LLM port.
2. **Agree with the owner what it is,** asking what you can't read in the spec:
   - what it does, and for whom; a change of scope starts in `spec/product.md`;
   - its name, one lowercase word, and its endpoints;
   - what it reaches: a service of its own, local, in the cloud or both, behind a port with an adapter and a fake; or only the core, as chat reaches the LLM;
   - whether it needs a piece another module holds: by the recipe, that piece moves to the core first;
   - whether it has a page in the web UI.
3. **Lay out each choice** with two to four options, the evidence and a recommendation, as the `next-step` skill does, and let the owner pick. Record the picks with the `decide` skill, and add the module's steps to `spec/plan.md`, as a phase of its own.
4. **Build it in small commits,** in the recipe's order: the backend with its tests, its services and settings, its demo, its CI, its page, its docs. Regenerate the API's schema and the web UI's types after an endpoint changes. Each setting gets a working default, and a line in `.env.example`.
5. **Check it:**
   - the gates, as `AGENTS.md`'s commands say: the check that each module has its places is among them;
   - its demo and its live tests against the real service, through the backend and through the web UI's origin;
   - the module turned off by its switch alone, `<NAME>_ENABLED=0`, its services with it.

   Show the real output.
6. **Explain what was built and why,** with links to the lines, and ask before the next step.
