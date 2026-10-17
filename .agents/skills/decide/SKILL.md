---
name: decide
description: Write a decision record in spec/decisions/ from decision-template.md, with the context, what was chosen, the alternatives and why not, the consequences and the assumptions still to verify, and add it to the index. Use when the owner has made a choice that shapes the app, or asks to record one.
---

# Record a decision

1. **Number it:** the highest number in `spec/decisions/`, plus one, in four digits. The title states the decision, such as "Store files in an object store"; the file is `NNNN-the-title-in-lowercase-with-hyphens.md`.
2. **Copy `spec/decisions/decision-template.md`, and fill in every section:**
   - **Context:** the problem, the requirements in play, and the facts known now.
   - **Decision:** what was chosen, in the first sentence, then the details that matter.
   - **Alternatives considered:** each option the owner was offered, and why it wasn't chosen.
   - **Consequences:** what becomes easier or harder, and the work it creates.
   - **Assumptions to verify:** what the decision relies on that nobody has measured yet. Tick one only with its evidence.
   - **Sources:** links, measurements and files.
3. **Set its status:**
   - Proposed, until the commit that implements it;
   - Accepted, if this commit implements it too.

   Date it today.
4. **If it replaces an earlier record:**
   - the new one says "Supersedes" and links to it;
   - the old one's status becomes "Superseded by", linking back, and gets a "Why it was superseded" section.

   Never rewrite an old record's decision.
5. **If it changes one of the template's foundations,** update that section of `docs/foundations.md` in the same commit.
6. **Add its row** to the table in `spec/decisions/README.md`.
7. **Commit it** on its own, or with the change it justifies.
