import os
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Default test environment so importing `app.*` modules never fails for lack of
# required settings. Individual tests override via monkeypatch where relevant.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_employee_platform",
)
os.environ.setdefault("LOG_LEVEL", "INFO")

from app.db.session import get_engine, get_sessionmaker  # noqa: E402


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    async with get_sessionmaker()() as session:
        yield session


@pytest.fixture
async def clean_db() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE TABLE application.messages, "
                "application.conversations, application.sessions CASCADE"
            )
        )
