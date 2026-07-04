# 0003 — Finance Simulator Over Real ERP

## Status

Accepted

## Context

The MVP's objective is to validate whether an AI assistant can reliably
understand finance questions, select correct tools, reason over data, and
avoid hallucination — not to prove out an ERP integration. Real ERP
systems (SAP, Oracle, Microsoft Dynamics, ERPNext, Odoo) introduce
security review, legal agreements, data privacy constraints, inconsistent
or unrepeatable datasets, and long integration lead times, all of which
are orthogonal to AI quality.

## Decision

Build a Finance Simulation Environment — a seeded, PostgreSQL-backed
fictional company (customers, vendors, invoices, purchase orders,
payments, expense claims) — as the sole data source for the MVP. The
simulator is treated as the ERP: everything must work against it, and if
it doesn't work with the simulator, it doesn't work (Principle 7).

## Alternatives Considered

- **Sandbox/demo instance of a real ERP** (e.g., an ERPNext or Odoo demo
  tenant). Rejected: still couples MVP progress to a third-party system's
  availability, data model quirks, and licensing, without solving the
  reproducibility problem needed for evaluation regression testing.
- **Static fixture/mock JSON files** with no real database. Rejected:
  would let the tool layer skip real query logic, hiding the exact
  problems (schema design, repository/service boundaries) that need to be
  solved before any future ERP integration.
- **Live customer ERP under NDA**. Rejected outright for MVP development —
  introduces data privacy, security, and legal exposure with no benefit to
  answering the MVP's core question.

## Rationale

A simulator gives full control over realistic-but-messy data (duplicate
invoices, PO mismatches, credit-limit breaches, extremely overdue
invoices) that real evaluation scenarios require, reproducibility via
seeded generation so bugs and evaluation results are stable across runs,
and freedom to model customer/vendor behavioral personas and scenario
packs (Healthy Company, Cash Flow Crisis, Rapid Growth, Fraud Detection)
that would be impossible to arrange safely against a real company.
Critically, the simulator is exposed only through adapter-style interfaces
(e.g. `InvoiceAdapter`, `CustomerAdapter`) that mirror what a real ERP
adapter would expose, so the AI and service layers never know they're
talking to a simulator.

## Consequences

- A dedicated data generator must be built and maintained, including
  seeded reproducibility and multiple dataset sizes (small/medium/large)
  and scenario packs — this is real engineering effort, not a shortcut.
- Replacing the simulator with ERPNext, SAP, or another real system later
  should only require new adapter implementations behind the same
  interfaces; services, tools, and the AI layer should not need to change
  (Principle 13, Principle 16).
- Any capability that only makes sense against a real ERP's operational
  quirks (e.g., vendor-specific approval workflows) is out of scope until
  a real integration is undertaken — the simulator does not need to model
  every ERP feature, only what the MVP's tools require.
