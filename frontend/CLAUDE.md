# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
npm run dev        # Start dev server (Vite, http://localhost:5173)
npm run build      # Type-check + production build
npm run lint       # ESLint
npm run preview    # Preview production build
```

No test runner is configured yet. Install Vitest/Playwright when adding tests.

## Project Overview

**InsureBot SG** — a frontend prototype for a multi-agent AI chatbot with generative UI for Singapore insurance advisory. This repo is the React frontend only (Sprint 1 Track C per `ARCHITECTURE.md`). All backend communication is mocked; real WebSocket/SSE integration is out of scope for this phase.

Tech stack: React 19 + TypeScript + Vite + Tailwind CSS v4 + lucide-react

## Architecture

### View State Machine

`App.tsx` owns all top-level state and drives a simple two-view state machine:

- `'start'` → `ChatStartScreen` (centered welcome, input, quick actions)
- `'chat'` → `ChatPanel` (message list + input)

When a message triggers canvas content (keywords: `canvas`, `illustrate`, `visuali`), `hasCanvas` is set to `true` and the sidebar auto-collapses.

### Layout

```
MainLayout
├── Sidebar          (collapsible; icon-only when collapsed)
└── flex container
    ├── [children]   (ChatStartScreen or ChatPanel)
    └── CanvasPanel  (shown only when hasCanvas=true; closes to restore sidebar)
```

`MainLayout` receives `sidebarCollapsed` and `hasCanvas` as props — it does not own state.

### Component Layers

| Layer | Path | Responsibility |
|-------|------|---------------|
| Layout | `src/components/layout/` | `AppShell`, `MainLayout` — structural shells |
| Chat | `src/components/chat/` | `ChatStartScreen`, `ChatPanel`, `ChatInput`, `MessageBubble`, `ThinkingSection` |
| Canvas | `src/components/canvas/` | `CanvasPanel` — hardcoded visualization (Agent Architecture demo) |
| Sidebar | `src/components/sidebar/` | `Sidebar` — collapsible nav |
| UI | `src/components/ui/` | `IconButton`, `Divider` — primitives |

### Key Types (`src/types/index.ts`)

```typescript
interface Message {
  id: string;
  role: 'user' | 'bot';
  content: string;
  hasCanvas?: boolean;   // triggers CanvasPanel when true
  thinking?: string;     // collapsible thinking section in bot messages
}
type AppView = 'start' | 'chat';
```

### Mocks (`src/mocks/messages.ts`)

Two fixture arrays stand in for real API responses:
- `textOnlyMessages` — text-only bot reply with a `thinking` field
- `canvasMessages` — bot reply with `hasCanvas: true`

The canvas keyword detection in `App.tsx` selects which mock to load.

## Design Conventions

- Background: `#f8f9fa` (gray-50)
- Sidebar: white with `border-gray-200`
- Primary blue: `#1a73e8` (input ring, active nav)
- User bubble: `gray-100`; bot text: `gray-900` / `gray-500`
- All layout uses Tailwind utility classes; avoid inline styles except for the background color constant above

## Reference Files

- `ARCHITECTURE.md` — full system architecture including the LangGraph multi-agent backend (FastAPI + Qdrant + Claude API)
- `implementation_plans/example_screen_implementation_plan.md` — the original 5-agent build plan for this Sprint 1 frontend
- `example_screens/` — PNG references for all four screen states (start, text-only, canvas+sidebar hidden, canvas+sidebar shown)
