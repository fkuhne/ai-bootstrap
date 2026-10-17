---
name: next-step
description: Prepare the plan's next step. Read the first unticked step in spec/plan.md and everything it touches, then lay out its choices with evidence and a recommendation for the owner to pick, before writing any code. Use when the owner asks what's next, or to start the next step.
---

# Prepare the next step

1. **Find the step:** the first unticked one in `spec/plan.md`. Read what it touches:
   - `spec/product.md`, and the rows of `spec/requirements.md` it serves;
   - the decision records it names, from `spec/decisions/`;
   - the sections of `docs/foundations.md` it changes or relies on;
   - the code it will change.
2. **If the step has no design choices,** say in a few lines what it will build, and how it will be checked, and ask whether to go ahead.
3. **Otherwise, lay out each choice:**
   - two to four options, each with what it costs and what it gives;
   - the evidence: measure, run or read the documentation where you can, and say what comes from memory alone;
   - a recommendation, with its reason.

   Keep it short; a table often helps.
4. **Stop, and let the owner pick.** Write no code and no record before the pick.
5. **After the pick:**
   - record the decision, with the `decide` skill;
   - build the step in small commits, each a coherent increment, none referencing a file that arrives later;
   - run the gates, as `AGENTS.md`'s commands say, and show their real output;
   - tick the step in the commit that finishes it;
   - explain what was built and why, with links to the lines, and ask before starting the next step.
