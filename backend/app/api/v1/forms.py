from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies.auth import require_auth
from app.schemas.common import UserContext
from app.schemas.form import Form, FormSubmitRequest
from app.services.form_service import FormService

router = APIRouter(prefix="/forms", tags=["forms"])
form_service = FormService()


@router.get("", response_model=list[Form])
async def list_forms(
    conversation_id: UUID | None = None,
    _: UserContext = Depends(require_auth),
) -> list[Form]:
    return await form_service.list_forms(conversation_id=conversation_id)


@router.get("/{form_id}", response_model=Form)
async def get_form(
    form_id: UUID,
    _: UserContext = Depends(require_auth),
) -> Form:
    form = await form_service.get_form(form_id)
    if form is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form not found")
    return form


@router.post("/{form_id}/submit", response_model=Form)
async def submit_form(
    form_id: UUID,
    payload: FormSubmitRequest,
    _: UserContext = Depends(require_auth),
) -> Form:
    form = await form_service.submit_form(form_id, payload.fields)
    if form is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form not found")
    return form
