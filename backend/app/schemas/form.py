from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class Form(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    conversation_id: UUID
    status: str = "pending"
    fields: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class FormSubmitRequest(BaseModel):
    fields: dict[str, Any] = Field(default_factory=dict)
