import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.errors import (
    AIError,
    BusinessError,
    InfrastructureError,
    ValidationError,
    register_exception_handlers,
)


def build_app_that_raises(exc: Exception) -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    async def boom() -> None:
        raise exc

    return app


async def get_response(app: FastAPI):
    # raise_app_exceptions=False: ServerErrorMiddleware re-raises after sending its
    # response (so real servers can log it); for these tests we only care about the
    # response it already sent.
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get("/boom")


@pytest.mark.asyncio
async def test_validation_error_maps_to_422() -> None:
    response = await get_response(build_app_that_raises(ValidationError("bad input")))
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["category"] == "validation"
    assert body["error"]["message"] == "bad input"


@pytest.mark.asyncio
async def test_business_error_maps_to_409() -> None:
    response = await get_response(build_app_that_raises(BusinessError("already paid")))
    assert response.status_code == 409
    assert response.json()["error"]["category"] == "business"


@pytest.mark.asyncio
async def test_infrastructure_error_maps_to_503() -> None:
    response = await get_response(build_app_that_raises(InfrastructureError("db down")))
    assert response.status_code == 503
    assert response.json()["error"]["category"] == "infrastructure"


@pytest.mark.asyncio
async def test_ai_error_maps_to_502() -> None:
    response = await get_response(build_app_that_raises(AIError("llm unavailable")))
    assert response.status_code == 502
    assert response.json()["error"]["category"] == "ai"


@pytest.mark.asyncio
async def test_unexpected_error_maps_to_500_with_generic_message() -> None:
    response = await get_response(build_app_that_raises(RuntimeError("boom, secret detail")))
    assert response.status_code == 500
    body = response.json()
    assert body["error"]["category"] == "unexpected"
    # the raw exception text must never leak to the user
    assert "secret detail" not in body["error"]["message"]


@pytest.mark.asyncio
async def test_error_response_includes_request_id_when_present() -> None:
    from app.core.logging import request_id_ctx_var
    from app.middleware.request_context import RequestContextMiddleware

    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)

    @app.get("/boom")
    async def boom() -> None:
        raise BusinessError("nope")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/boom", headers={"X-Request-ID": "fixed-id"})

    assert response.json()["error"]["request_id"] == "fixed-id"
    assert request_id_ctx_var.get() is None
