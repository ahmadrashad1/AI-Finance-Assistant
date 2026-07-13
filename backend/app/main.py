from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router
from app.api.health import router as health_router
from app.api.trace import router as trace_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.tool_registry import get_tool_registry
from app.middleware.request_context import RequestContextMiddleware


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    # Forces tool registration to happen now, at startup, rather than lazily
    # on the first chat request - a malformed tool definition should fail
    # fast (ADR-0004), not surface as a runtime planner error.
    get_tool_registry()

    application = FastAPI(title="AI Employee Platform", version="0.1.0")
    # Added before RequestContextMiddleware so it wraps the request outermost and
    # CORS headers land on every response, including ones that error out deeper.
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.add_middleware(RequestContextMiddleware)
    register_exception_handlers(application)
    application.include_router(health_router, prefix="/api")
    application.include_router(chat_router, prefix="/api")
    application.include_router(trace_router, prefix="/api")
    return application


app = create_app()
