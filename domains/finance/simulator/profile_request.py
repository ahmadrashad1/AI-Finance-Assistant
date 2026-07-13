"""Profiles the query shapes a typical multi-tool chat turn issues
against the fully-seeded database, using EXPLAIN ANALYZE - run once
per milestone (or whenever a new tool's query shape changes) to
confirm no common filter is missing an index. Not imported by anything
else; a standalone diagnostic script, matching consistency_check.py's
own precedent.
"""
from __future__ import annotations

import asyncio

from sqlalchemy import text

from app.db.session import get_sessionmaker

# Findings from the 2026-07-14 run against the freshly-reseeded seed=42
# database (after ix_tool_executions_request_id landed):
# - get_unpaid_invoices / get_aging_report: Bitmap Index Scan on
#   ix_invoices_status - indexed.
# - get_overdue_invoices: Index Scan on ix_invoices_status - indexed.
# - find_duplicate_invoices: Seq Scan - correct, not a gap: the
#   status != 'cancelled' filter matches ~all rows (205 of 232), so a
#   full scan + sort is the planner's right choice for a query whose job
#   is to group the whole table.
# - search_customers ILIKE '%...%': Seq Scan - the known, accepted
#   limitation (a leading wildcard can't use a plain B-tree index;
#   pg_trgm is not worth it at this table's size of ~hundreds of rows).
# - tool_executions by request_id: ix_tool_executions_request_id exists
#   (confirmed via pg_indexes); the freshly-reseeded table is empty, so
#   the planner correctly picks a Seq Scan at 0 rows - the index engages
#   as the table grows, which is exactly why it was added.
QUERIES: dict[str, str] = {
    "get_unpaid_invoices (status + customer_id)": (
        "EXPLAIN ANALYZE SELECT * FROM finance.invoices "
        "WHERE status IN ('sent', 'partially_paid', 'overdue') "
        "ORDER BY due_date"
    ),
    "get_overdue_invoices (status only)": (
        "EXPLAIN ANALYZE SELECT * FROM finance.invoices "
        "WHERE status = 'overdue' ORDER BY due_date"
    ),
    "get_aging_report (full unpaid scan)": (
        "EXPLAIN ANALYZE SELECT * FROM finance.invoices "
        "WHERE status IN ('sent', 'partially_paid', 'overdue')"
    ),
    "find_duplicate_invoices (customer_id, total, issue_date grouping)": (
        "EXPLAIN ANALYZE SELECT * FROM finance.invoices "
        "WHERE status != 'cancelled' "
        "ORDER BY customer_id, total, issue_date"
    ),
    "search_customers (ILIKE partial match)": (
        "EXPLAIN ANALYZE SELECT * FROM finance.customers "
        "WHERE company_name ILIKE '%Anchor%'"
    ),
    "trace endpoint (tool_executions by request_id)": (
        "EXPLAIN ANALYZE SELECT * FROM application.tool_executions "
        "WHERE request_id = 'nonexistent-id-for-plan-shape-only'"
    ),
}


async def run_profile() -> None:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        for label, query in QUERIES.items():
            print(f"\n=== {label} ===")
            result = await session.execute(text(query))
            for row in result.all():
                print(row[0])


if __name__ == "__main__":
    asyncio.run(run_profile())
