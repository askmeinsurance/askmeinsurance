from datetime import datetime
from uuid import UUID

from app.schemas.conversation import Conversation, ConversationCreate
from app.services.supabase_client import get_supabase_client


class ConversationService:
    @staticmethod
    def _to_conversation(row: dict) -> Conversation:
        return Conversation(
            id=UUID(str(row["id"])),
            title=str(row.get("title") or "New conversation"),
            created_at=datetime.fromisoformat(str(row["created_at"]).replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(str(row["updated_at"]).replace("Z", "+00:00")),
        )

    async def list_conversations(self, *, user_id: str) -> list[Conversation]:
        client = get_supabase_client()
        response = (
            client.table("conversations")
            .select("id,title,created_at,updated_at")
            .eq("user_id", user_id)
            .order("updated_at", desc=True)
            .execute()
        )
        return [self._to_conversation(row) for row in (response.data or [])]

    async def create_conversation(self, payload: ConversationCreate, *, user_id: str) -> Conversation:
        client = get_supabase_client()
        response = (
            client.table("conversations")
            .insert(
                {
                    "user_id": user_id,
                    "title": payload.title,
                }
            )
            .execute()
        )
        rows = response.data or []
        if not rows:
            raise RuntimeError("Failed to create conversation")
        return self._to_conversation(rows[0])

    async def get_conversation(self, conversation_id: UUID, *, user_id: str) -> Conversation | None:
        client = get_supabase_client()
        response = (
            client.table("conversations")
            .select("id,title,created_at,updated_at")
            .eq("id", str(conversation_id))
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        if not rows:
            return None
        return self._to_conversation(rows[0])

    async def delete_conversation(self, conversation_id: UUID, *, user_id: str) -> bool:
        client = get_supabase_client()
        response = (
            client.table("conversations")
            .delete()
            .eq("id", str(conversation_id))
            .eq("user_id", user_id)
            .execute()
        )
        return bool(response.data)

    async def touch_conversation(self, conversation_id: UUID, *, user_id: str) -> Conversation | None:
        client = get_supabase_client()
        response = (
            client.table("conversations")
            .update({"updated_at": datetime.utcnow().isoformat()})
            .eq("id", str(conversation_id))
            .eq("user_id", user_id)
            .execute()
        )
        rows = response.data or []
        if not rows:
            return None
        return self._to_conversation(rows[0])


conversation_service = ConversationService()
