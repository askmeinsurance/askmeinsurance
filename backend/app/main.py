from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette import status
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR

from app.api.v1.chat import router as chat_router
from app.api.v1.conversations import router as conversations_router
from app.api.v1.forms import router as forms_router
from app.schemas.common import ErrorEnvelope


def _status_error_code(status_code: int) -> str:
    return f"HTTP_{status_code}"


def _build_error_envelope(*, status_code: int, message: str, detail: Any) -> ErrorEnvelope:
    return ErrorEnvelope(
        error={
            "code": _status_error_code(status_code),
            "message": message,
            "detail": detail,
        }
    )


def create_app() -> FastAPI:
    app = FastAPI(title="AskMeInsurance API", version="0.1.0")

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail
        message = detail if isinstance(detail, str) else status.HTTP_STATUS_CODES.get(exc.status_code, "Request failed")
        envelope = _build_error_envelope(status_code=exc.status_code, message=message, detail=detail)
        return JSONResponse(status_code=exc.status_code, content=envelope.model_dump(), headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def request_validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
        envelope = _build_error_envelope(
            status_code=status_code,
            message="Request validation failed",
            detail=exc.errors(),
        )
        return JSONResponse(status_code=status_code, content=envelope.model_dump())

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
        status_code = HTTP_500_INTERNAL_SERVER_ERROR
        envelope = _build_error_envelope(
            status_code=status_code,
            message="Internal server error",
            detail=None,
        )
        return JSONResponse(status_code=status_code, content=envelope.model_dump())

    app.include_router(chat_router, prefix="/api/v1")
    app.include_router(conversations_router, prefix="/api/v1")
    app.include_router(forms_router, prefix="/api/v1")
    return app


app = create_app()
