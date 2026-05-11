from uuid import UUID

from app.schemas.conversation import ConversationMessage


class MessageService:
    def __init__(self) -> None:
        self._messages_by_conversation: dict[UUID, list[ConversationMessage]] = {}

    async def list_messages(self, conversation_id: UUID) -> list[ConversationMessage]:
        return list(self._messages_by_conversation.get(conversation_id, []))

    async def add_message(self, message: ConversationMessage) -> ConversationMessage:
        items = self._messages_by_conversation.setdefault(message.conversation_id, [])
        items.append(message)
        return message


message_service = MessageService()
