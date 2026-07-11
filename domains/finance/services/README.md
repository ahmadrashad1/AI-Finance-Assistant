# Finance Services

Business logic lives here: `InvoiceService`, `CustomerService`,
`VendorService`, `ReportService`, and friends. Services may collaborate with
each other; they never know about HTTP, the LLM, or prompts. Repositories
(data access) are called from services, not from tools.

`InvoiceService` (Milestone 5, extended in Milestone 6) covers Accounts
Receivable: unpaid/overdue/search invoice queries and per-customer
balances. `VendorService` (Milestone 6) is the first Accounts Payable
service: `get_vendor_balance` approximates a vendor's outstanding balance
from open purchase orders (`OUTSTANDING_PO_STATUSES`), since the simulator
has no vendor-invoice/vendor-payment tables yet. Both call repositories
directly - neither executes SQL itself.
