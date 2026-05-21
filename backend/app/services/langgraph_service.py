from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID

import httpx
from langchain_core.messages import AIMessage, HumanMessage

from app.core.config import Settings, get_settings
from app.schemas.chat import ChatEvent
from app.services.message_service import MessageService, message_service
from app.src.graph import get_compiled_graph


class LangGraphService:
    def __init__(
        self,
        settings: Settings | None = None,
        message_store: MessageService | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._message_store = message_store or message_service

    async def _call_gemini_once(self, message: str) -> str:
        api_key = self._settings.gemini_api_key
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")

        model = self._settings.gemini_model
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": message}],
                }
            ]
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, params={"key": api_key}, json=payload)
            response.raise_for_status()
            data = response.json()

        candidates = data.get("candidates") or []
        if not candidates:
            raise RuntimeError("Gemini response did not contain candidates")
        content = candidates[0].get("content") or {}
        parts = content.get("parts") or []
        text = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
        if not text.strip():
            raise RuntimeError("Gemini response did not contain text output")
        return text

    async def generate_conversation_title(self, first_message: str) -> str:
        prompt = (
            "Create a concise chat title (max 7 words) for this first user message. "
            "Return only the title, no quotes, no punctuation at the end.\n\n"
            f"Message: {first_message}"
        )
        if self._settings.gemini_api_key:
            return await self._call_gemini_once(prompt)
        return ""

    @staticmethod
    def _chunk_text(text: str, size: int = 180) -> list[str]:
        return [text[i : i + size] for i in range(0, len(text), size)] or [""]

    async def stream_chat(
        self,
        *,
        message: str,
        conversation_id: UUID | None,
        user: Any,
    ) -> AsyncGenerator[ChatEvent, None]:
        graph = await get_compiled_graph()

        history = []
        if conversation_id and user:
            raw = await self._message_store.list_messages(
                conversation_id, user_id=user.user_id
            )
            # Exclude the current user message already stored by ChatService
            if raw and raw[-1].role == "user" and raw[-1].content == message:
                raw = raw[:-1]
            history = [
                HumanMessage(content=m.content) if m.role == "user" else AIMessage(content=m.content)
                for m in raw
            ]

        yield ChatEvent(
            event="meta",
            data={
                "conversation_id": str(conversation_id) if conversation_id else None,
                "model": "langgraph/main_agent",
                "user_present": user is not None,
            },
        )

        try:
            result = await graph.ainvoke(
                {
                    "messages": [HumanMessage(content=message)],
                    "conversation_history": history,
                }
            )
            final_messages = result.get("messages", [])
            answer = final_messages[-1].content if final_messages else "No response generated."
        except Exception:  # noqa: BLE001
            answer = "I couldn't generate a response right now. Please try again in a moment."

        for piece in self._chunk_text(answer):
            yield ChatEvent(event="chunk", data={"text": piece})

        yield ChatEvent(event="done", data={"reason": "completed"})
