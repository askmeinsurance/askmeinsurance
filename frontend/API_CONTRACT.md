# Frontend Backend API Contract (Design-Derived)

This contract is inferred from the current frontend UX and state model.

- Source of truth: current frontend behavior and types in `frontend/src`
- Out of scope: current `backend` implementation
- Base URL (suggested): `/api`
- Content type: `application/json`
- Auth: not specified yet (add bearer/session later)

## Conventions

- IDs are opaque strings.
- Timestamps are ISO-8601 strings.
- `role` is one of `user | bot`.
- Error shape (recommended):

```json
{
  "error": {
    "code": "string",
    "message": "string",
    "details": {}
  }
}
```

## OpenAPI-Style Endpoint Summary

### 1) Create conversation

`POST /api/conversations`

Request body (optional):

```json
{
  "title": "string"
}
```

Response `201`:

```json
{
  "id": "conv_123",
  "title": "New chat",
  "createdAt": "2026-05-11T10:00:00Z",
  "updatedAt": "2026-05-11T10:00:00Z"
}
```

---

### 2) List conversations (sidebar)

`GET /api/conversations`

Query params (optional):

- `limit` (number)
- `cursor` (string)

Response `200`:

```json
{
  "items": [
    {
      "id": "conv_123",
      "title": "Understanding life insurance",
      "createdAt": "2026-05-11T10:00:00Z",
      "updatedAt": "2026-05-11T10:20:00Z"
    }
  ],
  "nextCursor": "string-or-null"
}
```

---

### 3) Get messages for one conversation

`GET /api/conversations/{conversationId}/messages`

Path params:

- `conversationId` (string)

Response `200`:

```json
{
  "items": [
    {
      "id": "msg_1",
      "role": "user",
      "content": "Can you compare term and whole life?",
      "createdAt": "2026-05-11T10:21:00Z"
    },
    {
      "id": "msg_2",
      "role": "bot",
      "content": "Sure, here are the key differences...",
      "thinking": "optional internal reasoning preview",
      "formRequest": null,
      "hasDiagram": false,
      "diagramTitle": null,
      "diagramData": null,
      "createdAt": "2026-05-11T10:21:03Z"
    }
  ]
}
```

---

### 4) Send message to conversation (recommended canonical chat endpoint)

`POST /api/conversations/{conversationId}/messages`

Path params:

- `conversationId` (string)

Request body:

```json
{
  "message": "string"
}
```

Response `200`:

```json
{
  "message": {
    "id": "msg_3",
    "role": "bot",
    "content": "I need a few details before I proceed.",
    "thinking": "optional",
    "formRequest": {
      "id": "insurance-intake-001",
      "title": "Insurance Planning Intake",
      "description": "Answer these short questions so I can tailor the recommendation.",
      "submitLabel": "Submit Details",
      "pages": [
        {
          "id": "profile",
          "title": "Profile Basics",
          "description": "Tell me who this plan is for.",
          "fields": [
            {
              "id": "fullName",
              "label": "Full Name",
              "type": "text",
              "required": true,
              "placeholder": "e.g. Alex Tan"
            }
          ]
        }
      ]
    },
    "hasDiagram": true,
    "diagramTitle": "System Prompt vs Skills",
    "diagramData": {
      "elements": [],
      "appState": {},
      "files": {}
    },
    "createdAt": "2026-05-11T10:22:00Z"
  }
}
```

Notes:

- `formRequest`, `diagramData`, and `thinking` are optional and can be `null`.
- This response shape directly matches the frontend `Message` union-like behavior.

---

### 5) Backward-compatible direct chat endpoint (optional)

If you want a non-conversation endpoint for simple integration:

`POST /api/chat`

Request body:

```json
{
  "conversationId": "conv_123",
  "message": "string"
}
```

Response: same as endpoint #4.

---

### 6) Submit dynamic form answers

`POST /api/form-submissions`

Request body:

```json
{
  "conversationId": "conv_123",
  "formId": "insurance-intake-001",
  "answers": {
    "fullName": "Alex Tan",
    "age": "35",
    "smoker": "non-smoker",
    "consent": true
  }
}
```

Response `200`:

```json
{
  "ok": true,
  "submissionId": "sub_123",
  "submittedAt": "2026-05-11T10:24:00Z"
}
```

---

### 7) Get diagram payload for canvas (optional if diagram already embedded in message)

`GET /api/diagrams/{diagramId}`

Response `200`:

```json
{
  "id": "diag_123",
  "title": "Financial Planning Diagram",
  "data": {
    "elements": [],
    "appState": {},
    "files": {}
  },
  "createdAt": "2026-05-11T10:25:00Z"
}
```

Alternative:

`GET /api/conversations/{conversationId}/diagrams/latest`

---

### 8) Stream chat response (optional for token/SSE UX)

`POST /api/conversations/{conversationId}/messages/stream`

- Transport: `text/event-stream`
- Events (recommended):
  - `token` (incremental text)
  - `message` (final message object matching endpoint #4)
  - `error`
  - `done`

---

### 9) Source lookup for citation click-through (future-ready)

`GET /api/source/{chunkId}`

Response `200`:

```json
{
  "chunkId": "chunk_abc",
  "pdfPath": "string",
  "pageNumber": 4,
  "bbox": {
    "x": 100,
    "y": 200,
    "width": 300,
    "height": 80
  }
}
```

## Schemas

### Message

```json
{
  "id": "string",
  "role": "user|bot",
  "content": "string",
  "thinking": "string|null",
  "formRequest": "FormRequest|null",
  "hasDiagram": "boolean",
  "diagramTitle": "string|null",
  "diagramData": "DiagramPayload|null",
  "createdAt": "ISO-8601"
}
```

### FormRequest

```json
{
  "id": "string",
  "title": "string",
  "description": "string|null",
  "submitLabel": "string|null",
  "pages": [
    {
      "id": "string",
      "title": "string",
      "description": "string|null",
      "fields": [
        {
          "id": "string",
          "label": "string",
          "type": "text|textarea|select|radio|checkbox",
          "required": true,
          "placeholder": "string|null",
          "options": [
            { "label": "string", "value": "string" }
          ]
        }
      ]
    }
  ]
}
```

### DiagramPayload

```json
{
  "elements": [],
  "appState": {},
  "files": {}
}
```

## Status Codes

- `200` OK
- `201` Created
- `400` Validation error
- `401` Unauthorized (if auth enabled)
- `404` Not found
- `409` Conflict
- `422` Semantic validation failure
- `500` Internal error

## Frontend Mapping Notes

- `ChatInput` submit -> endpoint #4 or #5
- Sidebar history -> endpoint #2
- Opening a past chat -> endpoint #3
- New chat button -> endpoint #1
- Form modal submit -> endpoint #6
- Canvas rendering -> `message.diagramData` or endpoint #7
- Thinking foldout -> `message.thinking`

## Minimal MVP Backend Surface

If you want to start very lean while preserving current UI capabilities:

1. `POST /api/conversations`
2. `GET /api/conversations`
3. `GET /api/conversations/{conversationId}/messages`
4. `POST /api/conversations/{conversationId}/messages`
5. `POST /api/form-submissions`

Everything else can be phased in later.
