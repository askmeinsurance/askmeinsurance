# Vercel Generative UI on Canvas Panel — Implementation Notes

## Context

The canvas panel (`src/components/canvas/CanvasPanel.tsx`) is intended to display generative UI driven by AI responses. The plan is to use Vercel AI SDK's generative UI approach (render-json / `useObject`) to stream structured JSON from an LLM and render it dynamically in the canvas.

---

## Core Compatibility Issue: Vite vs Next.js

Vercel's primary generative UI primitives (`streamUI`, `createStreamableUI`) are built on **React Server Components (RSC)**, which only works in **Next.js**.

The current project is a **Vite + React SPA** — RSC is not available.

### Client-Side Alternative (works with Vite)

The Vercel AI SDK provides a client-side hook that does not require RSC:

- **`useObject`** — streams a structured JSON object from an API endpoint, progressively hydrating a typed object as tokens arrive
- The canvas renders the streamed JSON using a schema-driven component renderer

This is a viable approach without migrating to Next.js.

---

## What Needs to Change

| Current State | Target State |
|---|---|
| `CanvasPanel` renders hardcoded static cards | `CanvasPanel` accepts a typed `canvasData` prop and renders dynamically |
| `Message.hasCanvas?: boolean` | `Message.canvasData?: CanvasSchema` (streamed JSON object) |
| Keyword detection in `App.tsx` triggers canvas | API response drives canvas via streamed JSON schema |
| No backend | Needs an API route (`/api/chat`) that calls Claude/GPT with a defined output schema |

---

## What Can Stay

The following are framework-agnostic and do not need to change:

- `MainLayout` layout slot for the canvas panel
- Canvas panel header (Code / Preview / Share / Refresh / Maximize buttons)
- Sidebar collapse behavior when canvas opens
- `handleCanvasClose` logic in `App.tsx`

---

## Recommended Implementation Path

### 1. Define a `CanvasSchema`

Design a typed union schema representing the different UI blocks the LLM can generate:

```ts
// src/types/canvas.ts
type CanvasBlock =
  | { type: 'info_card'; title: string; body: string; tokens?: number }
  | { type: 'skill_list'; skills: { label: string; trigger: string; color: string }[] }
  | { type: 'token_meter'; label: string; usage_percent: number }

interface CanvasSchema {
  title: string;
  subtitle?: string;
  blocks: CanvasBlock[];
}
```

### 2. Add an API Route

A lightweight backend is required to call the LLM with the schema. Options:

- **Stay on Vite**: add Express or Hono as a local API server
- **Migrate to Next.js**: enables RSC streaming if desired later

The API route should call the LLM (e.g. Claude via Anthropic SDK) and use `streamObject` with the `CanvasSchema` Zod schema.

### 3. Use `useObject` in the Canvas

```ts
import { experimental_useObject as useObject } from 'ai/react';

const { object, submit, isLoading } = useObject({
  api: '/api/canvas',
  schema: canvasSchema, // Zod schema
});
```

### 4. Replace Static Components with Schema-Driven Renderers

Replace hardcoded `SystemPromptCard`, `AvailableSkillsCard`, `AgentBrainFooter` with a renderer that maps `CanvasBlock.type` to components:

```tsx
function CanvasBlockRenderer({ block }: { block: CanvasBlock }) {
  switch (block.type) {
    case 'info_card': return <InfoCard {...block} />;
    case 'skill_list': return <SkillList {...block} />;
    case 'token_meter': return <TokenMeter {...block} />;
  }
}
```

### 5. Update Message Type

```ts
// src/types/index.ts
interface Message {
  id: string;
  role: 'user' | 'bot';
  content: string;
  canvasData?: CanvasSchema; // replaces hasCanvas boolean
  thinking?: string;
}
```

---

## Key Decision

**Stay on Vite or migrate to Next.js?**

| | Vite + API server | Next.js |
|---|---|---|
| RSC / `streamUI` | No | Yes |
| `useObject` (client streaming) | Yes | Yes |
| Complexity | Lower | Higher |
| Future flexibility | Limited | Full Vercel AI SDK support |

If RSC-based streaming UI (server-rendered component trees) is a goal, Next.js is the better foundation. If `useObject` JSON streaming is sufficient, Vite is fine.
