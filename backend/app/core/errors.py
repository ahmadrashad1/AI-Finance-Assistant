import logging
from enum import StrEnum
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import request_id_ctx_var

logger = logging.getLogger("app.errors")


class ErrorCategory(StrEnum):
    VALIDATION = "validation"
    BUSINESS = "business"
    INFRASTRUCTURE = "infrastructure"
    AI = "ai"
    UNEXPECTED = "unexpected"


class AppError(Exception):
    """Base class for errors that carry a category and a safe, user-facing message."""

    category: ErrorCategory = ErrorCategory.UNEXPECTED
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR

    def __init__(self, user_message: str, *, developer_message: str | None = None) -> None:
        super().__init__(user_message)
        self.user_message = user_message
        self.developer_message = developer_message or user_message


class ValidationError(AppError):
    category = ErrorCategory.VALIDATION
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT


class BusinessError(AppError):
    category = ErrorCategory.BUSINESS
    status_code = status.HTTP_409_CONFLICT


class InfrastructureError(AppError):
    category = ErrorCategory.INFRASTRUCTURE
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE


class AIError(AppError):
    category = ErrorCategory.AI
    status_code = status.HTTP_502_BAD_GATEWAY


def _error_response(category: ErrorCategory, status_code: int, message: str) -> JSONResponse:
    body: dict[str, Any] = {"error": {"category": category.value, "message": message}}
    request_id = request_id_ctx_var.get()
    if request_id is not None:
        body["error"]["request_id"] = request_id
    return JSONResponse(status_code=status_code, content=body)


async def app_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    logger.error(
        "handled application error: category=%s detail=%s",
        exc.category.value,
        exc.developer_message,
    )
    return _error_response(exc.category, exc.status_code, exc.user_message)


async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    logger.warning("request validation failed: %s", exc.errors())
    return _error_response(
        ErrorCategory.VALIDATION,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "The request could not be validated. Please check your input and try again.",
    )


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    return _error_response(ErrorCategory.UNEXPECTED, exc.status_code, str(exc.detail))


async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unexpected error while handling request", exc_info=exc)
    return _error_response(
        ErrorCategory.UNEXPECTED,
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "Something went wrong on our end. Please try again shortly.",
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)
