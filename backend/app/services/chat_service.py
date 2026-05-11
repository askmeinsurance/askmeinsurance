from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID

from app.schemas.chat import ChatEvent
from app.schemas.conversation import ConversationCreate, ConversationMessage
from app.services.conversation_service import ConversationService, conversation_service
from app.services.langgraph_service import LangGraphService
from app.services.message_service import MessageService, message_service


class ChatService:
    def __init__(
        self,
        langgraph_service: LangGraphService | None = None,
        conversation_store: ConversationService | None = None,
        message_store: MessageService | None = None,
    ) -> None:
        self._langgraph_service = langgraph_service or LangGraphService()
        self._conversation_store = conversation_store or conversation_service
        self._message_store = message_store or message_service

    @staticmethod
    def _fallback_title(first_message: str) -> str:
        cleaned = " ".join(first_message.split())
        if not cleaned:
            return "New conversation"
        title = cleaned[:60].strip()
        if len(cleaned) > 60:
            title = f"{title}..."
        return title

    @staticmethod
    def _sanitize_title(candidate: str, first_message: str) -> str:
        value = " ".join(candidate.strip().split())
        if not value:
            return ChatService._fallback_title(first_message)
        value = value.strip("\"' ")
        value = value.rstrip(".!?,;:")
        if len(value.split()) > 7:
            value = " ".join(value.split()[:7])
        if len(value) > 80:
            value = value[:80].rstrip()
        return value or ChatService._fallback_title(first_message)

    async def _resolve_conversation(self, message: str, conversation_id: UUID | None) -> UUID:
        if conversation_id:
            touched = await self._conversation_store.touch_conversation(conversation_id)
            if touched is not None:
                return touched.id
        try:
            suggested = await self._langgraph_service.generate_conversation_title(message)
        except Exception:  # noqa: BLE001
            suggested = ""
        title = self._sanitize_title(suggested, message)
        created = await self._conversation_store.create_conversation(ConversationCreate(title=title))
        return created.id

    async def stream_chat(
        self,
        *,
        message: str,
        conversation_id: UUID | None,
        user: Any,
    ) -> AsyncGenerator[ChatEvent, None]:
        resolved_conversation_id = await self._resolve_conversation(message, conversation_id)
        await self._message_store.add_message(
            ConversationMessage(
                conversation_id=resolved_conversation_id,
                role="user",
                content=message,
            )
        )

        bot_text = ""
        async for event in self._langgraph_service.stream_chat(
            message=message,
            conversation_id=resolved_conversation_id,
            user=user,
        ):
            if event.event == "chunk":
                chunk = event.data.get("text")
                if isinstance(chunk, str):
                    bot_text += chunk
            yield event

        if bot_text.strip():
            await self._message_store.add_message(
                ConversationMessage(
                    conversation_id=resolved_conversation_id,
                    role="bot",
                    content=bot_text,
                )
            )
