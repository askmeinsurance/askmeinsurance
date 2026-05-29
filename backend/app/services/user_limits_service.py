from fastapi import HTTPException

from app.services.supabase_client import get_supabase_client

DEFAULT_MAX_CONVERSATIONS = 10
DEFAULT_MAX_MESSAGES = 100


class UserLimitsService:
    async def get_limits(self, user_id: str) -> tuple[int, int]:
        client = get_supabase_client()
        response = (
            client.table("user_limits")
            .select("max_conversations,max_messages")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        if not rows:
            return (DEFAULT_MAX_CONVERSATIONS, DEFAULT_MAX_MESSAGES)
        row = rows[0]
        return (int(row["max_conversations"]), int(row["max_messages"]))

    async def check_conversation_limit(self, user_id: str, *, is_super_user: bool = False) -> None:
        if is_super_user:
            return
        client = get_supabase_client()
        max_conversations, _ = await self.get_limits(user_id)
        response = (
            client.table("conversations")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .is_("archived_at", "null")
            .execute()
        )
        active_count = response.count or 0
        if active_count >= max_conversations:
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Conversation limit reached. You have reached the maximum of "
                    f"{max_conversations} conversations. "
                    f"Archive existing conversations to create new ones."
                ),
            )

    async def check_message_limit(self, user_id: str, *, is_super_user: bool = False) -> None:
        if is_super_user:
            return
        client = get_supabase_client()
        _, max_messages = await self.get_limits(user_id)
        response = (
            client.table("messages")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .eq("sender", "user")
            .execute()
        )
        message_count = response.count or 0
        if message_count >= max_messages:
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Message limit reached. You have reached the maximum of "
                    f"{max_messages} messages."
                ),
            )


user_limits_service = UserLimitsService()
