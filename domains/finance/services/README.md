# Finance Services

Business logic lives here: `InvoiceService`, `CustomerService`,
`VendorService`, `ReportService`, and friends. Services may collaborate with
each other; they never know about HTTP, the LLM, or prompts. Repositories
(data access) are called from services, not from tools.

`InvoiceService` (Milestone 5) is the first implementation: it defines
what "unpaid" means (`UNPAID_STATUSES`), computes `days_outstanding`, and
sorts results by materiality. It calls `InvoiceRepository` and
`CustomerRepository` directly - it never executes SQL itself.
