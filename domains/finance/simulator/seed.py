from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import text

from app.db.session import get_engine, get_sessionmaker
from domains.finance.simulator.constants import DEFAULT_SEED
from domains.finance.simulator.generator import SimulatorSeeder

FINANCE_TABLES = (
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
        seeder = SimulatorSeeder(session, seed=seed)
        await seeder.seed()
        await session.commit()
    print(f"Seeded Northwind Manufacturing Ltd. (seed={seed}).")


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
