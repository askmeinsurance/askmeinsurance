from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies.auth import require_auth
from app.schemas.common import UserContext
from app.schemas.conversation import Conversation, ConversationCreate
from app.services.conversation_service import ConversationService

router = APIRouter(prefix="/conversations", tags=["conversations"])
conversation_service = ConversationService()


@router.get("", response_model=list[Conversation])
async def list_conversations(
    _: UserContext = Depends(require_auth),
) -> list[Conversation]:
    return await conversation_service.list_conversations()


@router.post("", response_model=Conversation, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    payload: ConversationCreate,
    _: UserContext = Depends(require_auth),
) -> Conversation:
    return await conversation_service.create_conversation(payload)


@router.get("/{conversation_id}", response_model=Conversation)
async def get_conversation(
    conversation_id: UUID,
    _: UserContext = Depends(require_auth),
) -> Conversation:
    conversation = await conversation_service.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conversation


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: UUID,
    _: UserContext = Depends(require_auth),
) -> None:
    deleted = await conversation_service.delete_conversation(conversation_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
