# Example Screen Implementation Plan

## Context

This plan covers the frontend UI implementation for InsureBot SG (Sprint 1 Track C per `ARCHITECTURE.md`). The goal is to build the four screen states shown in `example_screens/` as static/mocked React components — wiring up real backend communication is out of scope here.

**Screen flow:**
1. User lands on the **Chat Start Screen** (centered welcome + input + quick actions)
2. After the AI responds with text-only → **Chat Without Canvas** (full-width chat, sidebar visible)
3. After the AI responds with a visualization → **Chat With Canvas, Sidebar Hidden** (three-panel split)
4. User clicks the hamburger icon → **Chat With Canvas, Sidebar Shown** (same split with expanded sidebar)

**Tech stack:** React 18 + TypeScript + Vite + Tailwind CSS

---

## Screen Reference Summary

| Screen | File | Key Characteristics |
|--------|------|---------------------|
| Start | `chat_start_screen.png` | Centered layout, "Where should we start?", text input, quick-action buttons |
| Text-only response | `chat_without_canvas.png` | Left sidebar expanded, full-width chat, no canvas |
| With canvas (sidebar hidden) | `chat_with_elements_on_canvas_sidebar_hidden.png` | Icon-only sidebar, chat left, canvas right |
| With canvas (sidebar shown) | `chat_with_elements_on_canvas_sidebar_shown.png` | Expanded sidebar, chat center, canvas right |

---

## Implementation Agents

The five agents below must be executed **in order** — each builds on the previous.

---

### Agent 1 — Project Foundation

**Scope:** Initialize the project and establish shared design tokens and primitives.

**Tasks:**
1. Scaffold project: `npm create vite@latest . -- --template react-ts`
2. Install: `tailwindcss`, `postcss`, `autoprefixer`, `lucide-react`
3. Configure `tailwind.config.ts` with color palette matching screens:
   - Background: `gray-50` (#f8f9fa)
   - Sidebar: `white` with `gray-200` border
   - Primary blue: `#1a73e8` (input ring, active nav)
   - User bubble: `gray-100`; Text: `gray-900` / `gray-500`
4. Create `src/` folder structure:
   ```
   src/
   ├── components/
   │   ├── sidebar/
   │   ├── chat/
   │   ├── canvas/
   │   └── ui/
   ├── hooks/
   ├── types/
   ├── mocks/
   └── App.tsx
   ```
5. Create `src/types/index.ts`:
   - `Message` (`id`, `role: 'user' | 'bot'`, `content`, `hasCanvas?: boolean`)
   - `AppView` (`'start' | 'chat'`)
6. Create `src/components/ui/IconButton.tsx`, `Divider.tsx`
7. Create `src/mocks/messages.ts` — sample conversation data for all screens

**Files produced:**
- `vite.config.ts`, `tailwind.config.ts`, `postcss.config.js`
- `src/types/index.ts`, `src/mocks/messages.ts`
- `src/components/ui/IconButton.tsx`, `Divider.tsx`
- `src/App.tsx` (bare shell)

---

### Agent 2 — App Shell & Sidebar

**Prerequisite:** Agent 1 complete.

**Scope:** Persistent collapsible sidebar and top-level layout shell.

**Tasks:**
1. Create `src/components/sidebar/Sidebar.tsx`:
   - Props: `collapsed: boolean`, `onToggle: () => void`
   - Collapsed (~56px): icons only — hamburger, nav icons
   - Expanded (~260px): icons + labels
   - Expanded content: "InsureBot SG" title, "New chat" button, "My stuff", "Chats" section with mock history list, "Settings and help" pinned to bottom
   - Active item: `blue-50` bg + `blue-600` text
   - Transition: `transition-all duration-200`
2. Create `src/components/layout/AppShell.tsx`:
   - Manages `sidebarCollapsed` state (default: `false`)
   - Renders `<Sidebar>` (left) + `<main>` (fill remainder)
3. Update `src/App.tsx` to render `<AppShell>`

**Files produced:**
- `src/components/sidebar/Sidebar.tsx`
- `src/components/layout/AppShell.tsx`
- Updated `src/App.tsx`

---

### Agent 3 — Chat Start Screen

**Prerequisite:** Agent 2 complete.

**Scope:** Landing screen (`chat_start_screen.png`).

**Reference:** Gray `#f8f9fa` bg, centered content, greeting + headline, pill input, two rows of quick-action buttons.

**Tasks:**
1. Create `src/components/chat/ChatStartScreen.tsx`:
   - Props: `onSubmit: (message: string) => void`
   - `flex flex-col items-center justify-center h-full`
   - Greeting: "Hi [User]" (`gray-500`) + "Where should we start?" (large `gray-900`)
   - Quick action buttons: "Create image", "Create music", "Help me learn", "Write anything" / "Boost my day", "Create a video"
2. Create `src/components/chat/ChatInput.tsx`:
   - Props: `value`, `onChange`, `onSubmit`, `placeholder`
   - Pill-shaped input with send button — reused in chat panel
3. Update `src/App.tsx`: `view: AppView` state, transitions to `'chat'` on submit

**Files produced:**
- `src/components/chat/ChatStartScreen.tsx`
- `src/components/chat/ChatInput.tsx`
- Updated `src/App.tsx`

---

### Agent 4 — Chat Panel

**Prerequisite:** Agent 3 complete.

**Scope:** Chat message panel for all post-start screens.

**Reference:** `chat_without_canvas.png`, `chat_with_elements_on_canvas_sidebar_hidden.png`

**Tasks:**
1. Create `src/components/chat/ChatPanel.tsx`:
   - Props: `messages: Message[]`, `onSend: (text: string) => void`, `hasCanvas: boolean`
   - Full-height flex column: scrollable messages + pinned input
   - `hasCanvas=false` → full width; `hasCanvas=true` → ~40% width
2. Create `src/components/chat/MessageBubble.tsx`:
   - User: right-aligned `gray-100` pill
   - Bot: left-aligned, no bubble, full-width formatted text + bot icon, includes `ThinkingSection`
3. Create `src/components/chat/ThinkingSection.tsx`:
   - "Show thinking ▼" — collapsed by default
   - `ChevronDown` from `lucide-react`, `blue-600` accent
4. Simple text formatting: headings → `font-semibold`, bullets → `ul/li`, bold → `font-medium`
5. Input area: reuse `ChatInput` + "Tools" pill button (left) + "Fast" indicator (right)

**Files produced:**
- `src/components/chat/ChatPanel.tsx`
- `src/components/chat/MessageBubble.tsx`
- `src/components/chat/ThinkingSection.tsx`

---

### Agent 5 — Canvas Panel & Full Integration

**Prerequisite:** Agent 4 complete.

**Scope:** Canvas panel + wire all four screens together.

**Reference:** `chat_with_elements_on_canvas_sidebar_hidden.png`, `chat_with_elements_on_canvas_sidebar_shown.png`

**Tasks:**
1. Create `src/components/canvas/CanvasPanel.tsx`:
   - Props: `visible: boolean`
   - `visible=false` → renders `null`
   - `visible=true` → right panel ~60% width, `gray-200` left border
   - Header: title + Code / Preview / Share icon buttons
   - Body: static mock card ("Agent Skill vs. System Prompt", two sub-cards, dark footer bar)
2. Create `src/components/layout/MainLayout.tsx`:
   - Props: `sidebarCollapsed`, `onSidebarToggle`, `hasCanvas`, `children`
   - CSS flex: sidebar + chat area + canvas panel
3. Update `src/App.tsx` full state machine:
   ```
   view: 'start' | 'chat'
   messages: Message[]
   hasCanvas: boolean
   sidebarCollapsed: boolean
   ```
   - On submit: append messages, set `hasCanvas`, auto-collapse sidebar when canvas appears
   - Four screen states produced by different state combinations (see Screen Reference Summary)
4. Update `index.html` title to "InsureBot SG"

**Files produced:**
- `src/components/canvas/CanvasPanel.tsx`
- `src/components/layout/MainLayout.tsx`
- Updated `src/App.tsx`, `index.html`

---

## Dependency Graph

```
Agent 1 (Foundation)
    └── Agent 2 (Shell & Sidebar)
            └── Agent 3 (Start Screen)
                    └── Agent 4 (Chat Panel)
                            └── Agent 5 (Canvas + Integration)
```

---

## Verification Checklist

- [ ] `npm run dev` starts without errors
- [ ] **Start screen**: centered layout, greeting, input, 6 quick-action buttons
- [ ] **Text-only chat**: sidebar expanded, chat full-width, no canvas, "Show thinking" toggle works
- [ ] **Canvas hidden**: icon-only sidebar, chat ~40%, canvas visible on right
- [ ] **Canvas shown**: clicking hamburger expands sidebar, chat + canvas remain visible
- [ ] Sidebar toggle animates smoothly
- [ ] `npm run build` completes with zero TypeScript errors

---

## Notes for Agent Handoff

- Each agent runs `npm run build` before declaring done
- Use `lucide-react` for all icons (installed in Agent 1)
- No real API calls or SSE — all data from `src/mocks/messages.ts`
- Canvas body is a static mock in Sprint 1; real `ComponentSpec` rendering is Sprint 3 scope
- All state updates must return new objects (immutability — no in-place mutation)
- Keep each component file under 200 lines; extract sub-components as needed

---
