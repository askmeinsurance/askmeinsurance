from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID

from app.schemas.chat import ChatEvent
from app.services.langgraph_service import LangGraphService


class ChatService:
    def __init__(self, langgraph_service: LangGraphService | None = None) -> None:
        self._langgraph_service = langgraph_service or LangGraphService()

    async def stream_chat(
        self,
        *,
        message: str,
        conversation_id: UUID | None,
        user: Any,
    ) -> AsyncGenerator[ChatEvent, None]:
        async for event in self._langgraph_service.stream_chat(
            message=message,
            conversation_id=conversation_id,
            user=user,
        ):
            yield event
