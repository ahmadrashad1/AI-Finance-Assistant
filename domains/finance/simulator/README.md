# Finance Simulation Environment

The development ERP for the AI Finance Assistant. Models a single fictional
company (customers, vendors, invoices, purchase orders, payments, expense
claims) with internally consistent, seeded, reproducible data — including
intentional messiness (duplicate invoices, PO mismatches, credit-limit
breaches) for evaluation purposes.

Exposes adapter-style interfaces (e.g. `InvoiceAdapter`, `CustomerAdapter`)
so that a real ERP (ERPNext, SAP, Oracle) can later be swapped in behind the
same interface without changing services or the AI layer.

No seed logic lives here yet — this is a placeholder for the data generator
described in the PRD (Chapter 11).
