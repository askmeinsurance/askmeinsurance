# AskMeInsurance Shared API Contract

This document is the single source of truth for the `frontend` and `backend` API integration.

- Contract version: `v1`
- Base path: `/api/v1`
- Content type: `application/json` (except SSE stream endpoint)
- Auth: Supabase user JWT bearer auth (see "Authentication" section)
- ID format: UUID string
- Timestamp format: ISO-8601 UTC (example: `2026-05-11T10:00:00Z`)

## Naming And Wire Format

- Wire payloads use `snake_case`.
- Backend returns `snake_case` fields.
- Frontend maps `snake_case` <-> app-level camelCase types where needed.

## Authentication

### Supabase Bearer Flow

1. Frontend signs in with Supabase Auth and obtains session tokens.
2. Frontend reads the Supabase `access_token` from the active session.
3. Frontend includes `Authorization: Bearer <supabase_access_token>` on backend API calls.
4. Backend verifies bearer token and derives user context used for authorization.

### Frontend Requirements

- Attach bearer header on all protected `/api/v1` requests.
- If backend returns `401`, frontend should treat the session/token as invalid or expired and prompt re-authentication.

## Error Contract

`4xx/5xx` responses use:

```json
{
  "error": {
    "code": "string",
    "message": "string",
    "detail": {}
  }
}
```

Notes:
- Current backend default FastAPI errors return `{ "detail": "..." }`.
- To fully align, backend should normalize errors to this shape.

## Canonical Endpoints

### Conversations

1. `GET /api/v1/conversations`
- Response `200`:

```json
[
  {
    "id": "8dc8f808-8a66-4d70-bdd7-c2a4d2db5d3f",
    "title": "Term plan follow-up",
    "created_at": "2026-05-11T10:00:00Z",
    "updated_at": "2026-05-11T10:05:00Z"
  }
]
```

2. `POST /api/v1/conversations`
- Request:

```json
{
  "title": "New conversation"
}
```

- Response `201`: `Conversation` object (same shape as above)

3. `GET /api/v1/conversations/{conversation_id}`
- Response `200`: `Conversation`
- Response `404`: error

4. `DELETE /api/v1/conversations/{conversation_id}`
- Response `204`
- Response `404`: error

### Chat Stream (SSE)

5. `POST /api/v1/chat/stream`
- Request:

```json
{
  "message": "Help me compare whole life vs term",
  "conversation_id": "8dc8f808-8a66-4d70-bdd7-c2a4d2db5d3f"
}
```

- `conversation_id` optional
- Response: `text/event-stream`

SSE event schema:

1) `event: meta`
`data`:

```json
{
  "conversation_id": "uuid-or-null",
  "model": "string",
  "user_present": true
}
```

2) `event: chunk`
`data`:

```json
{
  "text": "partial token text"
}
```

3) `event: form_requested`
`data`:

```json
{
  "form_id": "f1a9f6de-4d4d-42d5-b893-c783f6f32641",
  "conversation_id": "8dc8f808-8a66-4d70-bdd7-c2a4d2db5d3f",
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
          "required": true,
          "placeholder": "e.g. Alex Tan",
          "options": []
        }
      ]
    }
  ]
}
```

4) `event: done`
`data`:

```json
{
  "reason": "completed"
}
```

### Forms

7. `GET /api/v1/forms?conversation_id={uuid}`
- Query `conversation_id` optional
- Response `200`:

```json
[
  {
    "id": "f1a9f6de-4d4d-42d5-b893-c783f6f32641",
    "conversation_id": "8dc8f808-8a66-4d70-bdd7-c2a4d2db5d3f",
    "status": "pending",
    "fields": {},
    "created_at": "2026-05-11T10:01:00Z",
    "updated_at": "2026-05-11T10:02:00Z"
  }
]
```

8. `GET /api/v1/forms/{form_id}`
- Response `200`: `Form`
- Response `404`: error

9. `POST /api/v1/forms/{form_id}/submit`
- Request:

```json
{
  "fields": {
    "full_name": "Alex Tan",
    "smoker": false
  }
}
```

- Response `200`: updated `Form` object with `status: "submitted"`
- Response `404`: error

## Shared Schemas

### Conversation

```json
{
  "id": "uuid",
  "title": "string",
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601"
}
```

### Form

```json
{
  "id": "uuid",
  "conversation_id": "uuid",
  "status": "pending|submitted",
  "fields": {},
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601"
}
```

### Form Request Payload (used in `form_requested` SSE event)

```json
{
  "form_id": "uuid",
  "conversation_id": "uuid",
  "title": "string",
  "description": "string",
  "submit_label": "string",
  "pages": [
    {
      "id": "string",
      "title": "string",
      "description": "string",
      "fields": [
        {
          "id": "string",
          "label": "string",
          "type": "text|textarea|select|radio|checkbox",
          "required": true,
          "placeholder": "string",
          "options": [
            { "label": "string", "value": "string" }
          ]
        }
      ]
    }
  ]
}
```

## Reconciliation Matrix (Current Drift -> Contract Decision)

1. Base path
- Current frontend: `/api/v1`
- Current backend: `/api/v1`
- Decision: keep `/api/v1` (already aligned)

2. `chunk` event payload
- Current frontend parser expects `data.chunk`
- Current backend emits `data.text`
- Decision: contract uses `data.text`; frontend parser should read `text`

3. `form_requested` event payload
- Current frontend expects `data.form_request` with paginated form schema
- Current backend emits `form_type` and `required_fields`
- Decision: contract requires full form payload (schema above) directly in `data`

4. Form identifier mapping
- Current frontend submits `formRequest.id` to `/forms/{id}/submit`
- Current contract uses backend form UUID in `form_id` and frontend maps to modal `id`
- Decision: frontend should store server `form_id` for submission

5. Error response shape
- Current backend: FastAPI default `detail`
- Decision: standardize to `{ error: { code, message, detail } }` for predictable FE handling

6. Naming convention
- Current frontend app types: camelCase (`conversationId`, `submitLabel`)
- Current backend: snake_case (`conversation_id`, `submit_label`)
- Decision: wire format stays snake_case; FE maps in API layer

## Implementation Checklist

### Must Fix First

1. Frontend SSE parsing
- Read `chunk` text from `data.text`
- Parse `form_requested` from canonical full payload

2. Backend `form_requested` producer
- Emit full form payload with `form_id` and `pages[]`
- Ensure emitted `form_id` is persisted in `FormService`

3. Shared typing
- Add shared TS types in frontend API client for wire payloads (snake_case)
- Add mapper to UI types (`form_id` -> `id`, `submit_label` -> `submitLabel`)

### Next (Stability)

4. Backend error normalization middleware/handler
- Convert `HTTPException` and validation errors to contract error shape

5. Contract tests
- Backend API tests for endpoint and SSE event schemas
- Frontend integration tests for stream parsing and form submission path
