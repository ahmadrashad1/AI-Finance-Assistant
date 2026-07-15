from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import text

from app.db.session import get_engine, get_sessionmaker
from domains.finance.simulator.constants import DEFAULT_SEED
from domains.finance.simulator.expectations import DEFAULT_EXPECTATIONS_PATH, write_expectations
from domains.finance.simulator.generator import SimulatorSeeder
from domains.finance.simulator.generator_v2 import SimulatorSeederV2

FINANCE_TABLES = (
    "finance.bank_transactions",
    "finance.payroll_lines",
    "finance.payroll_runs",
    "finance.close_tasks",
    "finance.close_periods",
    "finance.tax_periods",
    "finance.tax_rates",
    "finance.budgets",
    "finance.fixed_assets",
    "finance.requisition_items",
    "finance.purchase_requisitions",
    "finance.expense_limit_policies",
    "finance.approval_threshold_policies",
    "finance.expense_submission_policies",
    "finance.depreciation_policies",
    "finance.cash_transactions",
    "finance.bank_accounts",
    "finance.vendor_payments",
    "finance.vendor_invoices",
    "finance.payments",
    "finance.invoice_items",
    "finance.invoices",
    "finance.purchase_order_items",
    "finance.purchase_orders",
    "finance.expense_claims",
    "finance.employees",
    "finance.departments",
    "finance.products",
    "finance.customers",
    "finance.vendors",
)


async def run_seed(reset: bool, seed: int) -> None:
    engine = get_engine()
    if reset:
        async with engine.begin() as conn:
            await conn.execute(text(f"TRUNCATE TABLE {', '.join(FINANCE_TABLES)} CASCADE"))
    else:
        async with engine.connect() as conn:
            existing = await conn.execute(text("SELECT COUNT(*) FROM finance.customers"))
            if existing.scalar_one() > 0:
                print(
                    "finance.customers already has data. Re-run with --reset to replace it.",
                    file=sys.stderr,
                )
                sys.exit(1)

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        # Phase 1: the frozen v1 pipeline (must keep its exact RNG stream --
        # the evaluation cassettes were recorded against this data).
        seeder = SimulatorSeeder(session, seed=seed)
        await seeder.seed()
        # Phase 2: the v2 company extension, on a separate RNG stream.
        seeder_v2 = SimulatorSeederV2(session, seed=seed)
        expectations = await seeder_v2.seed()
        await session.commit()

    path = write_expectations(expectations, DEFAULT_EXPECTATIONS_PATH)
    print(f"Seeded Northwind Manufacturing Ltd. (seed={seed}).")
    print(f"Expectations written to {path}.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the Finance Simulation Environment.")
    parser.add_argument(
        "--reset", action="store_true", help="Truncate finance tables before seeding."
    )
    parser.add_argument(
        "--seed", type=int, default=DEFAULT_SEED, help=f"Random seed (default: {DEFAULT_SEED})."
    )
    args = parser.parse_args()
    asyncio.run(run_seed(reset=args.reset, seed=args.seed))


if __name__ == "__main__":
    main()
