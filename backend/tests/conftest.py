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

from app.db import session as session_module  # noqa: E402
from app.db.session import get_engine, get_sessionmaker  # noqa: E402


async def _dispose_and_reset_engine() -> None:
    # pytest-asyncio gives each test function its own event loop, but
    # `get_engine()` caches a single AsyncEngine (and asyncpg connection pool)
    # at module scope for the lifetime of the process. Disposing the pool
    # alone (`await get_engine().dispose()`) recreates the connection pool but
    # leaves the same `AsyncEngine` Python object (and the module-level
    # `_sessionmaker`) alive; once enough dispose-and-recreate cycles have
    # accumulated across a full suite run, some asyncpg/event-loop-bound state
    # apparently survives across those cycles and a stale connection object
    # (opened under some earlier loop) eventually attempts a graceful
    # close/cancel against a loop that's already closed, raising
    # `RuntimeError: Event loop is closed` during pool cleanup. Resetting the
    # module globals after disposal forces a brand new `AsyncEngine` and
    # `async_sessionmaker` to be constructed on the next test, matching the
    # precedent in `test_db_session.py`.
    await get_engine().dispose()
    session_module._engine = None
    session_module._sessionmaker = None


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    try:
        async with get_sessionmaker()() as session:
            yield session
    finally:
        await _dispose_and_reset_engine()


@pytest.fixture
async def clean_db() -> AsyncIterator[None]:
    # See the comment in `_dispose_and_reset_engine` above: the engine/pool is
    # cached at module scope but each test function gets its own event loop,
    # so any connections opened here must be disposed (and the engine/
    # sessionmaker globals reset) before the next test's loop tries to reuse
    # them. Tests that only depend on `clean_db` (e.g. HTTP-level tests that
    # exercise the app's own DB session rather than the `db_session` fixture)
    # would otherwise leak stale connections into the next test and fail with
    # "Event loop is closed".
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE TABLE evaluation.evaluation_results, evaluation.evaluation_runs, "
                "evaluation.evaluation_cases, "
                "application.tool_executions, application.messages, "
                "application.conversations, application.sessions, "
                "finance.vendor_payments, finance.vendor_invoices, "
                "finance.payments, finance.cash_transactions, finance.invoice_items, "
                "finance.invoices, finance.purchase_order_items, finance.purchase_orders, "
                "finance.expense_claims, finance.employees, finance.departments, "
                "finance.products, finance.customers, finance.vendors, finance.bank_accounts "
                "CASCADE"
            )
        )
    try:
        yield
    finally:
        await _dispose_and_reset_engine()
