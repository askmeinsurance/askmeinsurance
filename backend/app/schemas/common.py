from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class APIError(BaseModel):
    code: str
    message: str
    detail: Any | None = None


class HealthResponse(BaseModel):
    status: str = "ok"
    timestamp: datetime


class UserContext(BaseModel):
    model_config = ConfigDict(extra="allow")

    user_id: str
    email: str | None = None
    role: str | None = None
    is_super_user: bool = False
