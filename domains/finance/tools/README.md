# Finance Tools

One Python function per business capability (e.g. `get_unpaid_invoices()`,
`get_customer_balance()`, `find_duplicate_invoice()`). Tools:

- represent exactly one business capability,
- take explicit, typed parameters,
- return structured JSON (never prose),
- are deterministic and independently testable,
- never execute SQL and never call other tools directly (composition is the
  orchestration engine's job, not the tool layer's).

`get_unpaid_invoices` (Milestone 5) is the first implementation: it
validates its own parameters, calls `InvoiceService`, and returns
`{invoices: [...], summary: {count, total_outstanding}}`. It never touches
SQL and never calls another tool.

`search_invoices` (Milestone 6) is a flexible filter search: it validates
its own parameters, calls `InvoiceService.search_invoices`, and returns
`{invoices: [...], summary: {count, total_amount}}`.

`get_overdue_invoices` (Milestone 6) returns invoices with status
'overdue' specifically, sorted by days overdue (most urgent first); it
calls `InvoiceService.get_overdue_invoices` and returns `{invoices: [...],
summary: {count, total_outstanding}}`.

`get_customer_balance` (Milestone 6) resolves a customer by company name
(not business code - it's the one thing this tool is about), calls
`InvoiceService.get_customer_balance`, and returns a flat balance record
(no list/summary wrapper - there's only ever one customer per call).

`get_vendor_balance` (Milestone 6, upgraded in Milestone 7) is the first
Accounts Payable tool: it resolves a vendor by company name, calls
`VendorService.get_vendor_balance`, and returns a flat balance record
summed from that vendor's outstanding vendor invoices. Milestone 6
originally approximated this from open purchase orders before real
vendor invoices/payments existed; that approximation is gone now that
the real ledger does.

`get_cash_position` (Milestone 7) returns the company's current cash
balance from the real bank-account ledger (`CashRepository`). Takes no
parameters. Used alongside `get_vendor_invoices` when the user asks a
reasoning question with no single-tool answer (e.g. "which invoices
should I pay first?") - Phase 2 reasons over both results together.

`get_vendor_invoices` (Milestone 7) returns the company's outstanding
vendor invoices (status sent/partially_paid/overdue), sorted by due
date soonest-first, optionally filtered to one vendor by `vendor_id`
(business code). Used alongside `get_cash_position` for
payment-prioritization reasoning questions.
