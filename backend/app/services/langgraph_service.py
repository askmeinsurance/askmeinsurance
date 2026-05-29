from collections.abc import AsyncGenerator
import logging
import time
from typing import Any
from uuid import UUID

from langchain_core.messages import AIMessage, HumanMessage
from langfuse import get_client
from langfuse._client.propagation import propagate_attributes
from langfuse.langchain import CallbackHandler

from app.core.config import Settings, get_settings
from app.schemas.chat import ChatEvent
from app.services.message_service import MessageService, message_service
from app.agent.graph import get_compiled_graph
from app.agent.services.llm_service import extract_text_content, get_llm

logger = logging.getLogger("askmeinsurance.langgraph")


class LangGraphService:
    def __init__(
        self,
        settings: Settings | None = None,
        message_store: MessageService | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._message_store = message_store or message_service

    async def generate_conversation_title(self, first_message: str) -> str:
        if not self._settings.openrouter_api_key:
            return ""
        prompt = (
            "Create a concise chat title (max 7 words) for this first user message. "
            "Return only the title, no quotes, no punctuation at the end.\n\n"
            f"Message: {first_message}"
        )
        llm = get_llm("conversation_title")
        lf = get_client()
        with lf.start_as_current_observation(
            name="generate_conversation_title",
            as_type="generation",
            input=prompt,
        ) as gen:
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            result = extract_text_content(response.content)
            gen.update(output=result)
        return result

    @staticmethod
    def _chunk_text(text: str, size: int = 180) -> list[str]:
        return [text[i : i + size] for i in range(0, len(text), size)] or [""]

    def _sanitize_state_update(self, update: Any) -> Any:
        if not self._settings.langgraph_log_include_payloads:
            if isinstance(update, dict):
                return {"keys": sorted(str(k) for k in update.keys())}
            return {"type": type(update).__name__}

        excerpt_chars = max(self._settings.langgraph_log_state_excerpt_chars, 50)
        rendered = str(update)
        if len(rendered) > excerpt_chars:
            rendered = f"{rendered[:excerpt_chars]}..."
        return rendered

    async def stream_chat(
        self,
        *,
        message: str,
        conversation_id: UUID | None,
        user: Any,
        message_id: UUID | None = None,
        request_id: str | None = None,
    ) -> AsyncGenerator[ChatEvent, None]:
        graph = await get_compiled_graph()
        logger.setLevel(getattr(logging, self._settings.langgraph_log_level, logging.INFO))

        history = []
        if conversation_id and user:
            raw = await self._message_store.list_messages(
                conversation_id, user_id=user.user_id
            )
            # Exclude the current user message already stored by ChatService
            if raw and raw[-1].role == "user" and raw[-1].content == message:
                raw = raw[:-1]
            raw = raw[-5:]
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

        lf = get_client()
        trace_context = {"trace_id": message_id.hex} if message_id else None
        handler = CallbackHandler()
        started_at = time.perf_counter()
        last_node = "unknown"
        route = "unknown"
        correlation = {
            "request_id": request_id,
            "conversation_id": str(conversation_id) if conversation_id else None,
            "message_id": str(message_id) if message_id else None,
            "user_id": str(user.user_id) if user else None,
            "trace_id": message_id.hex if message_id else None,
        }
        logger.info("langgraph invoke started: %s", correlation)

        completed_with_fallback = False
        try:
            with lf.start_as_current_observation(
                name="stream_chat",
                as_type="span",
                trace_context=trace_context,
            ):
                with propagate_attributes(
                    session_id=str(conversation_id) if conversation_id else None,
                    user_id=str(user.user_id) if user else None,
                ):
                    input_payload = {
                        "messages": [HumanMessage(content=message)],
                        "conversation_history": history,
                    }
                    result = None
                    async for event in graph.astream_events(
                        input_payload,
                        config={"callbacks": [handler]},
                        version="v2",
                    ):
                        event_name = str(event.get("name", "unknown"))
                        event_type = str(event.get("event", "unknown"))
                        if event_type.endswith("_start"):
                            last_node = event_name
                        data = event.get("data")
                        if isinstance(data, dict):
                            output = data.get("output")
                            if isinstance(output, dict):
                                result = output
                                if output.get("route"):
                                    route = str(output["route"])
                                logger.debug(
                                    "langgraph event output: node=%s type=%s route=%s details=%s correlation=%s",
                                    event_name,
                                    event_type,
                                    route,
                                    self._sanitize_state_update(output),
                                    correlation,
                                )
            final_messages = []
            if isinstance(result, dict) and isinstance(result.get("messages"), list):
                final_messages = result["messages"]
            answer = (
                extract_text_content(final_messages[-1].content)
                if final_messages
                else "No response generated."
            )
            duration_ms = (time.perf_counter() - started_at) * 1000
            logger.info(
                "langgraph invoke completed: duration_ms=%.2f route=%s last_node=%s correlation=%s",
                duration_ms,
                route,
                last_node,
                correlation,
            )
        except Exception:  # noqa: BLE001
            duration_ms = (time.perf_counter() - started_at) * 1000
            logger.exception(
                "langgraph invoke failed: duration_ms=%.2f route=%s last_node=%s correlation=%s",
                duration_ms,
                route,
                last_node,
                correlation,
            )
            answer = "I couldn't generate a response right now. Please try again in a moment."
            completed_with_fallback = True

        for piece in self._chunk_text(answer):
            yield ChatEvent(event="chunk", data={"text": piece})

        yield ChatEvent(
            event="done",
            data={"reason": "failed_with_fallback" if completed_with_fallback else "completed"},
        )
