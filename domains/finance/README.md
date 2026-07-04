# Finance Domain

The first domain implementation on the AI Employee Platform. Contains
finance-specific tools, services, and the Finance Simulation Environment that
stands in for a real ERP during MVP development (see
`docs/adr/0003-finance-simulator-over-real-erp.md`).

- `tools/` — deterministic, business-named tool functions (e.g.
  `get_unpaid_invoices`, `find_duplicate_invoice`) that the platform's tool
  registry exposes to the planner. Tools call services only; no SQL, no
  prose generation, no state.
- `services/` — finance business logic (e.g. `InvoiceService`,
  `CustomerService`, `ReportService`). This is where "what counts as
  overdue" and "how is an aging report calculated" live — never in prompts.
- `simulator/` — the Finance Simulation Environment: seed data generation,
  customer/vendor personas, scenario packs, and the adapter interfaces that
  a future ERPNext/SAP/Oracle integration would implement in place of the
  simulator, without the AI or services noticing the difference.
