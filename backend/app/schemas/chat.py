from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


ChatEventType = Literal["meta", "chunk", "done"]


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    conversation_id: UUID | None = None


class ChatEvent(BaseModel):
    event: ChatEventType
    data: dict[str, Any]
