import logging
import time
from uuid import uuid4
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette import status
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR

from app.api.v1.chat import router as chat_router
from app.api.v1.conversations import router as conversations_router
from app.api.v1.forms import router as forms_router
from app.api.v1.auth import router as auth_router
from app.core.config import get_settings
from app.schemas.common import ErrorEnvelope

logger = logging.getLogger("askmeinsurance.api")
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


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
    settings = get_settings()
    app = FastAPI(title="AskMeInsurance API", version="0.1.0")
    print("[BOOT] AskMeInsurance backend app created", flush=True)

    allowed_origins = [origin.strip() for origin in settings.cors_allowed_origins.split(",") if origin.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    logger.info("CORS configured with allowed origins: %s", allowed_origins)
    print(f"[BOOT] CORS allowed origins: {allowed_origins}", flush=True)

    @app.middleware("http")
    async def request_logging_middleware(request: Request, call_next):
        request_id = str(uuid4())
        start = time.perf_counter()
        request.state.request_id = request_id
        print(f"[REQ:{request_id}] {request.method} {request.url.path} started", flush=True)
        logger.info(
            "[%s] request started: %s %s",
            request_id,
            request.method,
            request.url.path,
        )
        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start) * 1000
            logger.info(
                "[%s] request completed: %s %s -> %s (%.2fms)",
                request_id,
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
            )
            print(
                f"[REQ:{request_id}] {request.method} {request.url.path} -> {response.status_code}",
                flush=True,
            )
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception as exc:  # noqa: BLE001
            duration_ms = (time.perf_counter() - start) * 1000
            logger.exception(
                "[%s] request crashed: %s %s (%.2fms)",
                request_id,
                request.method,
                request.url.path,
                duration_ms,
            )
            print(
                f"[REQ:{request_id}] {request.method} {request.url.path} crashed: {type(exc).__name__}: {exc}",
                flush=True,
            )
            raise

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        detail = exc.detail
        message = detail if isinstance(detail, str) else status.HTTP_STATUS_CODES.get(exc.status_code, "Request failed")
        logger.warning(
            "[%s] http exception: %s %s -> %s (%s)",
            request_id,
            request.method,
            request.url.path,
            exc.status_code,
            message,
        )
        envelope = _build_error_envelope(status_code=exc.status_code, message=message, detail=detail)
        return JSONResponse(status_code=exc.status_code, content=envelope.model_dump(), headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def request_validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
        logger.warning(
            "[%s] request validation error: %s %s -> %s",
            request_id,
            request.method,
            request.url.path,
            exc.errors(),
        )
        envelope = _build_error_envelope(
            status_code=status_code,
            message="Request validation failed",
            detail=exc.errors(),
        )
        return JSONResponse(status_code=status_code, content=envelope.model_dump())

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        status_code = HTTP_500_INTERNAL_SERVER_ERROR
        logger.exception(
            "[%s] unhandled exception on %s %s",
            request_id,
            request.method,
            request.url.path,
            exc_info=exc,
        )
        envelope = _build_error_envelope(
            status_code=status_code,
            message="Internal server error",
            detail=None,
        )
        return JSONResponse(status_code=status_code, content=envelope.model_dump())

    app.include_router(chat_router, prefix="/api/v1")
    app.include_router(conversations_router, prefix="/api/v1")
    app.include_router(forms_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    return app


app = create_app()
