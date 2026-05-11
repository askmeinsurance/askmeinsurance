from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.dependencies.auth import require_auth
from app.core.sse import format_sse
from app.schemas.chat import ChatRequest
from app.schemas.common import UserContext
from app.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])
chat_service = ChatService()


@router.post("/stream")
async def stream_chat(
    payload: ChatRequest,
    current_user: UserContext = Depends(require_auth),
) -> StreamingResponse:
    async def event_stream() -> AsyncGenerator[str, None]:
        async for event in chat_service.stream_chat(
            message=payload.message,
            conversation_id=payload.conversation_id,
            user=current_user,
        ):
            yield format_sse(event.event, event.data)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
