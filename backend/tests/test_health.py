import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import check_database_connection
from app.main import app


@pytest.mark.asyncio
async def test_health_reports_healthy_when_database_ok() -> None:
    app.dependency_overrides[check_database_connection] = lambda: True
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy", "app": "ok", "database": "ok"}
    finally:
        app.dependency_overrides.pop(check_database_connection, None)


@pytest.mark.asyncio
async def test_health_reports_degraded_when_database_unavailable() -> None:
    app.dependency_overrides[check_database_connection] = lambda: False
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {
            "status": "degraded",
            "app": "ok",
            "database": "unavailable",
        }
    finally:
        app.dependency_overrides.pop(check_database_connection, None)
