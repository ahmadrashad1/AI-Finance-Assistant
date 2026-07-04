# Finance Services

Business logic lives here: `InvoiceService`, `CustomerService`,
`VendorService`, `ReportService`, and friends. Services may collaborate with
each other; they never know about HTTP, the LLM, or prompts. Repositories
(data access) are called from services, not from tools.

No application logic lives here yet — this is a placeholder for
implementation once the platform skeleton is in place.
