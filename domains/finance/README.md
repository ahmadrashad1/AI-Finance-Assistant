# Finance Domain

The first domain implementation on the AI Employee Platform. Contains
finance-specific tools, services, and the Finance Simulation Environment that
stands in for a real ERP during MVP development (see
`docs/adr/0003-finance-simulator-over-real-erp.md`).

- `tools/` — 11 deterministic, business-named tool functions (e.g.
  `get_unpaid_invoices`, `find_duplicate_invoices`, `get_aging_report`,
  `search_customers`) that the platform's tool registry exposes to the
  planner. Tools call services only; no SQL, no prose generation, no state.
- `services/` — finance business logic (e.g. `InvoiceService`,
  `VendorService`). This is where "what counts as overdue" and "how is an
  aging report calculated" live — never in prompts.
- `repositories/` — the only layer that touches SQL/SQLAlchemy for finance
  data (e.g. `InvoiceRepository`, `CustomerRepository`).
- `models/` — SQLAlchemy models for the `finance` schema (customers,
  vendors, invoices, purchase orders, payments, expenses, cash, workforce).
- `simulator/` — the Finance Simulation Environment: the seeded fictional
  company (Northwind Manufacturing Ltd., seed=42), persona-driven data
  generation with intentional anomalies (duplicates, partial payments),
  and a consistency checker. A future ERPNext/SAP/Oracle integration
  replaces this behind the same service interfaces, without the AI
  noticing the difference.
