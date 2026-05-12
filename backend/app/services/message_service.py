from uuid import UUID

from app.schemas.conversation import ConversationMessage
from app.services.supabase_client import get_supabase_client


class MessageService:
    @staticmethod
    def _to_message(row: dict) -> ConversationMessage:
        sender = str(row.get("sender") or "assistant")
        role = "bot" if sender == "assistant" else "user"
        return ConversationMessage(
            id=UUID(str(row["id"])),
            conversation_id=UUID(str(row["conversation_id"])),
            role=role,
            content=str(row["content"]),
            created_at=row["created_at"],
        )

    async def list_messages(self, conversation_id: UUID, *, user_id: str) -> list[ConversationMessage]:
        client = get_supabase_client()
        response = (
            client.table("messages")
            .select("id,conversation_id,sender,content,created_at")
            .eq("conversation_id", str(conversation_id))
            .eq("user_id", user_id)
            .order("created_at", desc=False)
            .execute()
        )
        return [self._to_message(row) for row in (response.data or [])]

    async def add_message(self, message: ConversationMessage, *, user_id: str) -> ConversationMessage:
        client = get_supabase_client()
        sender = "assistant" if message.role == "bot" else "user"
        response = (
            client.table("messages")
            .insert(
                {
                    "conversation_id": str(message.conversation_id),
                    "user_id": user_id,
                    "sender": sender,
                    "content": message.content,
                }
            )
            .execute()
        )
        rows = response.data or []
        if not rows:
            raise RuntimeError("Failed to create message")
        return self._to_message(rows[0])


message_service = MessageService()
