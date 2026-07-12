# Finance Services

Business logic lives here: `InvoiceService`, `CustomerService`,
`VendorService`, `ReportService`, and friends. Services may collaborate with
each other; they never know about HTTP, the LLM, or prompts. Repositories
(data access) are called from services, not from tools.

`InvoiceService` (Milestone 5, extended in Milestone 6) covers Accounts
Receivable: unpaid/overdue/search invoice queries and per-customer
balances. `VendorService` (Milestone 6, upgraded in Milestone 7) is the
Accounts Payable service: `get_vendor_balance` sums a vendor's
outstanding vendor invoices (`OUTSTANDING_VENDOR_INVOICE_STATUSES`),
`get_cash_position` reports the company's cash ledger balance, and
`list_outstanding_vendor_invoices` backs the `get_vendor_invoices` tool.
Milestone 6 originally approximated vendor balance from purchase orders,
before real vendor invoices/payments existed; that approximation is
gone now that the real ledger does. Both services call repositories
directly - neither executes SQL itself.
