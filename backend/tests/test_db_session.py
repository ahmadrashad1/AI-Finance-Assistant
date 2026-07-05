import pytest

from app.db.session import check_database_connection


@pytest.mark.asyncio
async def test_check_database_connection_returns_false_when_unreachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:1/does_not_exist")
    from app.core.config import get_settings

    get_settings.cache_clear()
    from app.db import session as session_module

    session_module._engine = None
    try:
        assert await check_database_connection() is False
    finally:
        get_settings.cache_clear()
        session_module._engine = None
