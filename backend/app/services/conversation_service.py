from datetime import datetime
from uuid import UUID

from app.schemas.conversation import Conversation, ConversationCreate


class ConversationService:
    def __init__(self) -> None:
        self._store: dict[UUID, Conversation] = {}

    async def list_conversations(self) -> list[Conversation]:
        return sorted(self._store.values(), key=lambda item: item.updated_at, reverse=True)

    async def create_conversation(self, payload: ConversationCreate) -> Conversation:
        conversation = Conversation(title=payload.title)
        self._store[conversation.id] = conversation
        return conversation

    async def get_conversation(self, conversation_id: UUID) -> Conversation | None:
        return self._store.get(conversation_id)

    async def delete_conversation(self, conversation_id: UUID) -> bool:
        return self._store.pop(conversation_id, None) is not None

    async def touch_conversation(self, conversation_id: UUID) -> Conversation | None:
        conversation = self._store.get(conversation_id)
        if conversation is None:
            return None
        conversation.updated_at = datetime.utcnow()
        self._store[conversation_id] = conversation
        return conversation


conversation_service = ConversationService()
