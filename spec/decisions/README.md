# Decision records

This folder records every decision that shapes the app, one file per decision. Each record states:
- the context;
- what we chose;
- the alternatives, and why we rejected them;
- the consequences;
- the assumptions we still have to verify.

What the app is built on, and why, is in [`docs/foundations.md`](../../docs/foundations.md). Records start where the foundations end: a decision that changes one of them gets a record here, and the foundations page is updated.

**Statuses**
- **Proposed**: planned, but not yet confirmed by the owner or proven by an implementation. The commit that implements it flips it to Accepted, amending it if the implementation taught us something.
- **Accepted**: in force.
- **Superseded**: replaced by a later record, which it links to. It's kept for history.

**Adding a record**
1. Copy [`decision-template.md`](decision-template.md) to the next free number, e.g. `0001-short-title.md`.
2. Fill it in and add a row to the table below.
3. Commit it on its own, before or together with the change it justifies.

Don't rewrite a record to change its decision. Write a new record and mark the old one superseded. Ticking assumptions and adding evidence is fine. Never renumber: commits and other records cite records by number.

| # | Decision | Status | Date |
|---|---|---|---|
