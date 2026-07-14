const TOOL_PHRASES: Record<string, string> = {
  get_unpaid_invoices: "unpaid invoices",
  get_overdue_invoices: "overdue invoices",
  search_invoices: "invoice search",
  get_customer_balance: "customer balances",
  get_vendor_balance: "vendor balances",
  get_vendor_invoices: "vendor invoices",
  get_customer: "customer records",
  search_customers: "customer search",
  get_aging_report: "the aging report",
  find_duplicate_invoices: "the duplicate check",
  get_cash_position: "the cash ledger",
  get_current_date: "the calendar",
};

export function toolDisplayName(tool: string): string {
  return TOOL_PHRASES[tool] ?? "the ledgers";
}
