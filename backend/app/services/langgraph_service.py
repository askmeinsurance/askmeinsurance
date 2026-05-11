from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID

from app.schemas.chat import ChatEvent


class LangGraphService:
    async def stream_chat(
        self,
        *,
        message: str,
        conversation_id: UUID | None,
        user: Any,
    ) -> AsyncGenerator[ChatEvent, None]:
        yield ChatEvent(
            event="meta",
            data={
                "conversation_id": str(conversation_id) if conversation_id else None,
                "model": "dummy-langgraph",
                "user_present": user is not None,
            },
        )
        yield ChatEvent(event="chunk", data={"text": f"Echo: {message[:80]}"})
        yield ChatEvent(
            event="form_requested",
            data={
                "form_type": "insurance_intake",
                "required_fields": ["full_name", "date_of_birth", "coverage_goal"],
            },
        )
        yield ChatEvent(event="done", data={"reason": "completed"})
