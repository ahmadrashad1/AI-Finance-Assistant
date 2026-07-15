# 0008 — Single Configurable Simulation Clock

## Status

Accepted

## Context

Milestone 11 (Simulator v2, PRD Ch.19) adds time-dependent computations
that did not exist before: payroll periods, financial close periods, tax
periods, and depreciation, alongside the existing aging/overdue logic.
Before this milestone, "today" was resolved inconsistently — the seeder
used a hardcoded `SIMULATION_TODAY` constant in
`domains/finance/simulator/constants.py`, while services and repositories
(`InvoiceService`, `VendorService`, `PaymentRepository`,
`VendorPaymentRepository`) defaulted to `date.today()`, and the
`get_current_date` tool returned `datetime.now(UTC)`. This meant the
assistant's own sense of "today" could disagree with the date the seeded
data was generated against, and every new v2 invariant (payroll run
count, close-period contiguity, tax-period filing status) needed one
unambiguous, overridable answer to "what day is it."

## Decision

A single function, `simulation_today()`, is the only source of "today"
for business logic anywhere in the platform. It lives in
`ai_platform/simulation_clock.py` (platform-level, since the
`get_current_date` tool needs it and `ai_platform` cannot import
`domains`) and is re-exported from `domains/finance/simulation.py` for
finance code. It reads the `SIMULATION_TODAY` environment variable (ISO
date) and falls back to the fixed anchor `2026-07-08` otherwise. The
seeder's own `SIMULATION_TODAY` constant now resolves through this
function at import time, so the seeder, the consistency check, every
service, every repository, and the `get_current_date` tool all agree.

Every `date.today()` call in business logic (`InvoiceService`,
`VendorService`, `PaymentRepository`, `VendorPaymentRepository`,
`get_current_date`) was replaced with `simulation_today()`.

## Alternatives Considered

- **Keep `SIMULATION_TODAY` as a seeder-only constant, add a separate
  clock for services.** Rejected: this is exactly the pre-existing
  inconsistency that caused the problem — two independent "todays" that
  could drift if one were changed without the other.
- **Pass `today` explicitly through every call site instead of a global
  clock function.** Consistent with existing code (`as_of: date | None`
  parameters already exist on several services), but doesn't fix the
  *default* — callers that omit the parameter still need a single
  fallback, which is exactly what `simulation_today()` provides. The
  existing `as_of`/`today` optional parameters were kept; only their
  default value changed.
- **Read the env var directly wherever "today" is needed.** Rejected:
  duplicates the fallback-and-parse logic at every call site and makes it
  easy for one of them to drift (e.g. forgetting the fallback).

## Rationale

A living business simulation (PRD Ch.19: payroll, close periods, tax
periods, depreciation) has many more places that need to agree on "today"
than the invoice-only MVP did. Centralizing the definition makes it
structurally impossible for the seeder and a service to disagree, and
makes the date overridable (via `SIMULATION_TODAY`) without touching code
— useful for future work that advances the simulation clock forward
(PRD Ch.11's postponed "living business environment" idea).

## Consequences

- `get_current_date` now returns the simulation date, not the wall-clock
  date. Verified not to change eval scores (39/53, unchanged from
  baseline) — the tool's ISO-date shape is identical either way.
- Test files that asserted against `date.today()` were re-anchored to
  `simulation_today()` (`test_get_overdue_invoices_integration.py`,
  `test_get_customer_balance_integration.py`,
  `test_get_unpaid_invoices_integration.py`,
  `test_search_invoices_integration.py`,
  `test_get_cash_position_integration.py`, `test_vendor_service.py`).
- `domains/finance/simulator/constants.SIMULATION_TODAY` is still the
  name every generator module imports, but it is now a resolved value,
  not an independent hardcoded constant — changing `SIMULATION_TODAY` the
  env var changes what the seeder generates too, so seeding with a
  non-default simulation date requires a fresh `--reset` (documented in
  `backend/.env.example`).
