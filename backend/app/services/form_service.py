from datetime import datetime
from uuid import UUID

from app.schemas.form import Form


class FormService:
    def __init__(self) -> None:
        self._store: dict[UUID, Form] = {}

    async def list_forms(self, conversation_id: UUID | None = None) -> list[Form]:
        if conversation_id is None:
            return list(self._store.values())
        return [form for form in self._store.values() if form.conversation_id == conversation_id]

    async def get_form(self, form_id: UUID) -> Form | None:
        return self._store.get(form_id)

    async def upsert_form(self, form: Form) -> Form:
        form.updated_at = datetime.utcnow()
        self._store[form.id] = form
        return form

    async def submit_form(self, form_id: UUID, fields: dict[str, object]) -> Form | None:
        form = self._store.get(form_id)
        if form is None:
            return None
        form.fields.update(fields)
        form.status = "submitted"
        form.updated_at = datetime.utcnow()
        self._store[form_id] = form
        return form
