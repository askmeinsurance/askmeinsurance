from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID, uuid4

import httpx

from app.core.config import Settings, get_settings
from app.schemas.chat import ChatEvent
from app.schemas.form import Form
from app.services.form_service import FormService


class LangGraphService:
    def __init__(
        self,
        form_service: FormService | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._form_service = form_service or FormService()
        self._settings = settings or get_settings()

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
        form_conversation_id = conversation_id or uuid4()
        form = await self._form_service.upsert_form(Form(conversation_id=form_conversation_id))
        using_gemini = self._settings.llm_provider == "gemini"

        yield ChatEvent(
            event="meta",
            data={
                "conversation_id": str(conversation_id) if conversation_id else None,
                "model": self._settings.gemini_model if using_gemini else "dummy-langgraph",
                "user_present": user is not None,
            },
        )
        if using_gemini:
            try:
                response_text = await self._call_gemini_once(message)
            except Exception:  # noqa: BLE001
                response_text = (
                    "I couldn't get a response from Gemini right now. "
                    "Please try again in a moment."
                )
            for piece in self._chunk_text(response_text):
                yield ChatEvent(event="chunk", data={"text": piece})
        else:
            yield ChatEvent(event="chunk", data={"text": f"Echo: {message[:80]}"})

        yield ChatEvent(
            event="form_requested",
            data={
                "form_id": str(form.id),
                "conversation_id": str(form.conversation_id),
                "title": "Insurance Planning Intake",
                "description": "Answer these short questions so I can tailor the recommendation.",
                "submit_label": "Submit Details",
                "pages": [
                    {
                        "id": "profile",
                        "title": "Profile Basics",
                        "description": "Tell me who this plan is for.",
                        "fields": [
                            {
                                "id": "full_name",
                                "label": "Full Name",
                                "type": "text",
                                "required": True,
                                "placeholder": "e.g. Alex Tan",
                                "options": [],
                            },
                            {
                                "id": "date_of_birth",
                                "label": "Date of Birth",
                                "type": "text",
                                "required": True,
                                "placeholder": "YYYY-MM-DD",
                                "options": [],
                            },
                            {
                                "id": "coverage_goal",
                                "label": "Coverage Goal",
                                "type": "text",
                                "required": True,
                                "placeholder": "e.g. 500000",
                                "options": [],
                            },
                        ],
                    }
                ],
            },
        )
        yield ChatEvent(event="done", data={"reason": "completed"})
