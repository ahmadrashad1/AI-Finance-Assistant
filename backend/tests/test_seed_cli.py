from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_sessionmaker
from domains.finance.models import CustomerModel
from domains.finance.simulator.seed import run_seed


@pytest.mark.asyncio
async def test_run_seed_populates_customers(clean_db: None, db_session: AsyncSession) -> None:
    await run_seed(reset=True, seed=42)

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as verify_session:
        count = (
            await verify_session.execute(select(func.count()).select_from(CustomerModel))
        ).scalar_one()
    assert count == 25


@pytest.mark.asyncio
async def test_run_seed_refuses_without_reset_when_data_exists(
    clean_db: None, db_session: AsyncSession
) -> None:
    await run_seed(reset=True, seed=42)

    with pytest.raises(SystemExit):
        await run_seed(reset=False, seed=42)
