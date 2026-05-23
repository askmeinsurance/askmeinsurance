from collections.abc import AsyncGenerator
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.dependencies.auth import require_auth
from app.core.sse import format_sse
from app.schemas.chat import ChatRequest
from app.schemas.common import UserContext
from app.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])
chat_service = ChatService()
logger = logging.getLogger("askmeinsurance.chat")


@router.post("/stream")
async def stream_chat(
    payload: ChatRequest,
    request: Request,
    current_user: UserContext = Depends(require_auth),
) -> StreamingResponse:
    request_id = getattr(request.state, "request_id", None)
    logger.info(
        "chat stream requested: request_id=%s user_id=%s conversation_id=%s message_len=%s",
        request_id,
        current_user.user_id,
        payload.conversation_id,
        len(payload.message),
    )

    async def event_stream() -> AsyncGenerator[str, None]:
        event_count = 0
        try:
            async for event in chat_service.stream_chat(
                message=payload.message,
                conversation_id=payload.conversation_id,
                user=current_user,
                request_id=request_id,
            ):
                event_count += 1
                logger.debug("chat stream event: type=%s", event.event)
                yield format_sse(event.event, event.data)
            logger.info("chat stream completed: events=%s", event_count)
        except Exception:  # noqa: BLE001
            logger.exception("chat stream failed")
            raise

    return StreamingResponse(event_stream(), media_type="text/event-stream")
