import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import check_database_connection
from app.main import app


@pytest.mark.asyncio
async def test_cors_allows_the_configured_frontend_origin() -> None:
    app.dependency_overrides[check_database_connection] = lambda: True
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/health", headers={"Origin": "http://localhost:3000"}
            )
        assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    finally:
        app.dependency_overrides.pop(check_database_connection, None)


@pytest.mark.asyncio
async def test_cors_preflight_is_allowed_for_configured_origin() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
