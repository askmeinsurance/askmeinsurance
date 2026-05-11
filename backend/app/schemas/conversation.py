from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class Conversation(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    title: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ConversationCreate(BaseModel):
    title: str = Field(min_length=1)
