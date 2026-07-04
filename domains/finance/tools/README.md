# Finance Tools

One Python function per business capability (e.g. `get_unpaid_invoices()`,
`get_customer_balance()`, `find_duplicate_invoice()`). Tools:

- represent exactly one business capability,
- take explicit, typed parameters,
- return structured JSON (never prose),
- are deterministic and independently testable,
- never execute SQL and never call other tools directly (composition is the
  orchestration engine's job, not the tool layer's).

No application logic lives here yet — this is a placeholder for Milestone 3+
(see the PRD's development roadmap).
