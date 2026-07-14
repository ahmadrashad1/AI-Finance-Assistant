# Atelier Frontend Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the approved "Atelier" design (`docs/superpowers/specs/2026-07-14-atelier-frontend-redesign-design.md`): a dark, lamp-lit, serif-voiced workspace where prose lives in the dialogue and tables live in a summoned right-side drawer with RESULT/TRACE tabs.

**Architecture:** Presentation-only. Design tokens as CSS custom properties in `globals.css`; co-located CSS Modules per component (built into Next 15, no new runtime deps); fonts via `next/font/google` (Fraunces + JetBrains Mono, self-hosted at build). A pure string-splitting function in `markdown.ts` separates markdown tables from prose; `page.tsx` turns table segments into drawer artifacts. `lib/api-client.ts` and the backend are untouched.

**Tech Stack:** Next.js 15 (App Router), React 19, TypeScript strict, CSS Modules, `next/font`. No test runner exists in `frontend/` (deliberate, all 10 milestones) — verification is `npm run lint` + `npm run typecheck` + `npm run build` per task, plus a live Playwright walkthrough in the final task.

## Global Constraints

- **Zero changes** to `frontend/lib/api-client.ts` and zero backend changes.
- No new npm dependencies (CSS Modules and `next/font` ship with Next 15).
- Color rules from the spec, verbatim: brass `#C98A3D` is THE interactive accent; ember `#C96F3D` for overdue/risk ONLY; sage `#7FA07C` for paid/healthy ONLY; no purple anywhere.
- All animation is CSS-only and disabled under `@media (prefers-reduced-motion: reduce)`.
- Every figure/invoice-number/table-numeric renders in the mono font with `font-variant-numeric: tabular-nums`.
- The frontend decides nothing: table detection, numeric-column alignment, and status coloring are presentational string checks on what the backend already said.
- Copy, verbatim where specified: empty-state kicker "NORTHWIND MANUFACTURING · FINANCE", greeting "Good {morning|afternoon|evening}. The books are open.", input placeholder "Ask the books anything…", thinking line "Consulting the ledgers — {tool phrase}…", drawer affordance "on the desk →".
- Work on branch `atelier-frontend-redesign`. Commit per task. Don't push without being asked.
- After each task: `cd frontend && npm run lint && npm run typecheck && npm run build` must be clean.

## Existing code facts the implementer needs

- `app/page.tsx` (132 lines) holds all state; SSE loop handles `request_id`, `tool_call` (currently REPLACES message content with `Running {tool}…` — this plan removes that), `token`, `done`, `error` events from `streamChat(sessionId, message, conversationId)` in `lib/api-client.ts`.
- `components/chat/markdown.ts` exports `renderInlineMarkdown(text): string` (escape-then-transform; safe for `dangerouslySetInnerHTML`). Its internal helpers `parseTableRow`, `isTableRowLine`, `isSeparatorRow` already exist and are reused by the new splitter.
- `MessageBubble` currently renders `<strong>You/Assistant:</strong>` + inline HTML + an inline `TracePanel` toggle. `TracePanel` fetches `getTrace(requestId)` and renders plan branch/prompt versions/durations.
- ESLint/tsc are strict (`@typescript-eslint` with `exactOptionalPropertyTypes`-style unions like `requestId?: string | undefined` — mirror existing prop typing style).

---

### Task 1: Foundation — fonts, tokens, workspace shell

**Files:**
- Modify: `frontend/app/layout.tsx`
- Modify: `frontend/app/globals.css` (full rewrite)
- Modify: `frontend/app/page.tsx:113-131` (the JSX return only)
- Create: `frontend/app/page.module.css`

**Interfaces:**
- Produces: CSS variables `--room --wall --surface --surface-raised --seam --seam-strong --ink --ink-soft --pencil --pencil-faint --brass --ember --sage --font-serif --font-mono`, and `page.module.css` classes `workspace`, `dialogue`, `scroll`, `errorCard` that later tasks style against. Every later component may assume these variables exist.

- [ ] **Step 1: Create the branch**

```bash
cd "D:\New-Automation\AI-FinanceAssistant"
git checkout master && git checkout -b atelier-frontend-redesign
```

- [ ] **Step 2: Wire fonts in `app/layout.tsx`** (replace the whole file)

```tsx
import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Fraunces, JetBrains_Mono } from "next/font/google";

import "./globals.css";

const fraunces = Fraunces({
  subsets: ["latin"],
  variable: "--font-serif",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "AI Finance Assistant",
  description: "AI Finance Assistant — the first domain on the AI Employee Platform",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={`${fraunces.variable} ${jetbrainsMono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
```

- [ ] **Step 3: Rewrite `app/globals.css`** (replace the whole file)

```css
:root {
  color-scheme: dark;

  --room: #15110d;
  --wall: #1e1813;
  --surface: #211a14;
  --surface-raised: #241d16;
  --seam: #2c241c;
  --seam-strong: #3a2e22;
  --ink: #e8dfd3;
  --ink-soft: #d9c9a8;
  --pencil: #8a7a65;
  --pencil-faint: #6e5f4e;
  --brass: #c98a3d;
  --ember: #c96f3d;
  --sage: #7fa07c;

  --serif: var(--font-serif), Georgia, "Times New Roman", serif;
  --sans: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  --mono: var(--font-mono), "Courier New", monospace;

  --radius-card: 8px;
  --radius-chip: 14px;
  --shadow-card: 0 3px 8px rgba(0, 0, 0, 0.35);
  --shadow-drawer: -8px 0 18px rgba(0, 0, 0, 0.5);
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  background: var(--room);
  color: var(--ink);
  font-family: var(--sans);
}

:focus-visible {
  outline: 2px solid var(--brass);
  outline-offset: 2px;
}

button {
  font-family: var(--sans);
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation: none !important;
    transition: none !important;
  }
}
```

- [ ] **Step 4: Create `app/page.module.css`** (workspace shell + error card; drawer column is added in Task 6)

```css
.workspace {
  display: flex;
  height: 100vh;
  background:
    radial-gradient(ellipse 80% 60% at 50% 0%, #241c15 0%, transparent 60%),
    var(--wall);
  overflow: hidden;
}

.dialogue {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  padding: 1.25rem 2rem 1.5rem;
}

.scroll {
  flex: 1;
  overflow-y: auto;
  padding-right: 0.5rem;
}

.errorCard {
  background: var(--surface);
  border-left: 3px solid var(--ember);
  border-radius: var(--radius-card);
  color: var(--ink);
  font-size: 0.9rem;
  padding: 0.6rem 0.9rem;
  margin: 0.5rem 0;
}
```

- [ ] **Step 5: Swap the shell in `app/page.tsx`** — replace only the `return (...)` block (lines 113–131) and add the import:

```tsx
import styles from "./page.module.css";
```

```tsx
  return (
    <main className={styles.workspace}>
      <ConversationSidebar
        conversations={conversations}
        activeConversationId={activeConversationId}
        onSelect={handleSelectConversation}
        onNewConversation={handleNewConversation}
        disabled={isStreaming}
      />
      <section className={styles.dialogue}>
        <div className={styles.scroll}>
          <MessageList messages={messages} />
        </div>
        {error && <p className={styles.errorCard} role="alert">{error}</p>}
        <MessageInput disabled={isStreaming || !sessionId} onSend={handleSend} />
      </section>
    </main>
  );
```

(The `<h1>` heading is removed — the sidebar carries the identity from Task 3. Delete the now-unused `main { … }` / `table { … }` rules previously in `globals.css`; table styling returns scoped in Task 5.)

- [ ] **Step 6: Verify**

Run: `cd frontend && npm run lint && npm run typecheck && npm run build`
Expected: all clean. Then `npm run dev` briefly: dark room renders, chat still works end to end (old component styles are temporarily unstyled-on-dark — fine until Tasks 3–4).

- [ ] **Step 7: Commit**

```bash
git add frontend/app/layout.tsx frontend/app/globals.css frontend/app/page.tsx frontend/app/page.module.css
git commit -m "feat(frontend): Atelier foundation - fonts, design tokens, workspace shell"
```

---

### Task 2: `splitMessageContent` — pure prose/table splitter

**Files:**
- Modify: `frontend/components/chat/markdown.ts` (append; existing exports unchanged)

**Interfaces:**
- Produces (exact types later tasks import from `./markdown`):

```ts
export interface TableSegment {
  kind: "table";
  headerCells: string[];
  bodyRows: string[][];
}
export interface ProseSegment {
  kind: "prose";
  text: string;
}
export type MessageSegment = ProseSegment | TableSegment;
export function splitMessageContent(content: string): MessageSegment[];
export function deriveArtifactTitle(segments: MessageSegment[]): string;
```

- [ ] **Step 1: Append the splitter to `markdown.ts`** (reuses the file's existing `parseTableRow`, `isTableRowLine`, `isSeparatorRow` helpers)

```ts
export interface TableSegment {
  kind: "table";
  headerCells: string[];
  bodyRows: string[][];
}

export interface ProseSegment {
  kind: "prose";
  text: string;
}

export type MessageSegment = ProseSegment | TableSegment;

// Pure string splitting - no business rules. Walks the same GFM-table
// grammar renderInlineMarkdown uses, but returns structured segments so
// the UI can route prose to the dialogue and tables to the drawer.
export function splitMessageContent(content: string): MessageSegment[] {
  const lines = content.split("\n");
  const segments: MessageSegment[] = [];
  let proseBuffer: string[] = [];

  const flushProse = () => {
    const text = proseBuffer.join("\n").trim();
    if (text.length > 0) {
      segments.push({ kind: "prose", text });
    }
    proseBuffer = [];
  };

  let i = 0;
  while (i < lines.length) {
    const line = lines[i]!;
    const next = lines[i + 1];
    if (
      isTableRowLine(line) &&
      next !== undefined &&
      isTableRowLine(next) &&
      isSeparatorRow(parseTableRow(next))
    ) {
      flushProse();
      const headerCells = parseTableRow(line);
      const bodyRows: string[][] = [];
      let j = i + 2;
      while (j < lines.length && isTableRowLine(lines[j]!)) {
        bodyRows.push(parseTableRow(lines[j]!));
        j++;
      }
      segments.push({ kind: "table", headerCells, bodyRows });
      i = j;
    } else {
      proseBuffer.push(line);
      i++;
    }
  }
  flushProse();
  return segments;
}

// Drawer header: nearest prose line before the first table (last non-empty
// line, stripped of markdown emphasis/heading markers), else "Result".
export function deriveArtifactTitle(segments: MessageSegment[]): string {
  const firstTableIndex = segments.findIndex((s) => s.kind === "table");
  if (firstTableIndex > 0) {
    const before = segments[firstTableIndex - 1];
    if (before && before.kind === "prose") {
      const lines = before.text.split("\n").filter((l) => l.trim().length > 0);
      const last = lines[lines.length - 1];
      if (last) {
        const cleaned = last.replace(/^#+\s*/, "").replace(/\*\*/g, "").replace(/:\s*$/, "").trim();
        if (cleaned.length > 0 && cleaned.length <= 80) {
          return cleaned;
        }
      }
    }
  }
  return "Result";
}
```

- [ ] **Step 2: Verify types and grammar agreement**

Run: `cd frontend && npm run lint && npm run typecheck && npm run build`
Expected: clean. (No test runner exists; behavior is exercised live in Task 6 Step 6 and the Task 7 walkthrough, where the demo answer "Here are the unpaid invoices:" + table must produce 1 prose + 1 table segment and the title "Here are the unpaid invoices".)

- [ ] **Step 3: Commit**

```bash
git add frontend/components/chat/markdown.ts
git commit -m "feat(frontend): pure prose/table splitter for drawer artifacts"
```

---

### Task 3: Sidebar and input in Atelier dress

**Files:**
- Modify: `frontend/components/chat/ConversationSidebar.tsx` (full rewrite)
- Create: `frontend/components/chat/ConversationSidebar.module.css`
- Modify: `frontend/components/chat/MessageInput.tsx` (full rewrite)
- Create: `frontend/components/chat/MessageInput.module.css`

**Interfaces:**
- Consumes: token variables from Task 1.
- Produces: same component props as today (no signature changes): `ConversationSidebarProps`, `MessageInputProps`.

- [ ] **Step 1: Rewrite `ConversationSidebar.tsx`**

```tsx
import type { ConversationSummary } from "@/lib/api-client";

import styles from "./ConversationSidebar.module.css";

export interface ConversationSidebarProps {
  conversations: ConversationSummary[];
  activeConversationId: string | null;
  onSelect: (conversationId: string) => void;
  onNewConversation: () => void;
  disabled: boolean;
}

export function ConversationSidebar({
  conversations,
  activeConversationId,
  onSelect,
  onNewConversation,
  disabled,
}: ConversationSidebarProps) {
  return (
    <aside className={styles.rail}>
      <div className={styles.brand}>
        <span className={styles.lamp} aria-hidden="true">✦</span> Atelier
      </div>
      <ul className={styles.list}>
        {conversations.map((conversation) => (
          <li key={conversation.id}>
            <button
              onClick={() => onSelect(conversation.id)}
              disabled={disabled}
              className={
                conversation.id === activeConversationId ? styles.itemActive : styles.item
              }
            >
              {conversation.title ?? "New conversation"}
            </button>
          </li>
        ))}
      </ul>
      <button onClick={onNewConversation} disabled={disabled} className={styles.newButton}>
        + New conversation
      </button>
    </aside>
  );
}
```

- [ ] **Step 2: Create `ConversationSidebar.module.css`**

```css
.rail {
  width: 240px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--seam);
  background: var(--room);
  padding: 1rem 0.75rem;
}

.brand {
  font-family: var(--sans);
  font-size: 0.7rem;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: var(--pencil);
  padding: 0 0.5rem 1rem;
}

.lamp {
  color: var(--brass);
}

.list {
  flex: 1;
  list-style: none;
  margin: 0;
  padding: 0;
  overflow-y: auto;
}

.item,
.itemActive {
  width: 100%;
  text-align: left;
  background: transparent;
  border: none;
  border-radius: 6px;
  color: var(--pencil);
  cursor: pointer;
  font-size: 0.85rem;
  padding: 0.5rem 0.6rem;
  margin-bottom: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  transition: background 120ms ease, color 120ms ease;
}

.item:hover:not(:disabled) {
  background: var(--surface);
  color: var(--ink-soft);
}

.itemActive {
  background: var(--surface-raised);
  color: var(--ink-soft);
}

.item:disabled,
.itemActive:disabled,
.newButton:disabled {
  opacity: 0.5;
  cursor: default;
}

.newButton {
  background: transparent;
  border: 1px solid var(--seam-strong);
  border-radius: var(--radius-chip);
  color: var(--ink-soft);
  cursor: pointer;
  font-size: 0.8rem;
  padding: 0.45rem 0.75rem;
  margin-top: 0.75rem;
  transition: border-color 120ms ease, color 120ms ease;
}

.newButton:hover:not(:disabled) {
  border-color: var(--brass);
  color: var(--brass);
}
```

- [ ] **Step 3: Rewrite `MessageInput.tsx`**

```tsx
"use client";

import { useState } from "react";

import styles from "./MessageInput.module.css";

export interface MessageInputProps {
  disabled: boolean;
  onSend: (message: string) => void;
}

export function MessageInput({ disabled, onSend }: MessageInputProps) {
  const [value, setValue] = useState("");

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    const trimmed = value.trim();
    if (!trimmed || disabled) {
      return;
    }
    onSend(trimmed);
    setValue("");
  };

  return (
    <form onSubmit={handleSubmit} className={styles.form}>
      <input
        type="text"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder="Ask the books anything…"
        disabled={disabled}
        className={styles.input}
      />
      <button type="submit" disabled={disabled} className={styles.send} aria-label="Send">
        ↵
      </button>
    </form>
  );
}
```

- [ ] **Step 4: Create `MessageInput.module.css`**

```css
.form {
  display: flex;
  gap: 0.5rem;
  margin-top: 0.75rem;
}

.input {
  flex: 1;
  background: var(--surface);
  border: 1px solid var(--seam);
  border-radius: 18px;
  box-shadow: var(--shadow-card);
  color: var(--ink);
  font-family: var(--sans);
  font-size: 0.95rem;
  padding: 0.7rem 1.1rem;
  transition: border-color 120ms ease;
}

.input::placeholder {
  color: var(--pencil-faint);
  font-style: italic;
}

.input:focus {
  border-color: var(--brass);
  outline: none;
}

.send {
  background: var(--surface);
  border: 1px solid var(--seam-strong);
  border-radius: 50%;
  color: var(--brass);
  cursor: pointer;
  font-size: 1rem;
  width: 42px;
  height: 42px;
  transition: border-color 120ms ease, background 120ms ease;
}

.send:hover:not(:disabled) {
  border-color: var(--brass);
  background: var(--surface-raised);
}

.send:disabled {
  opacity: 0.5;
  cursor: default;
}
```

- [ ] **Step 5: Verify**

Run: `cd frontend && npm run lint && npm run typecheck && npm run build`
Expected: clean. Dev-run: rail shows "✦ ATELIER", active conversation highlighted, input is the rounded "Ask the books anything…" bar with the brass ↵.

- [ ] **Step 6: Commit**

```bash
git add frontend/components/chat/ConversationSidebar.tsx frontend/components/chat/ConversationSidebar.module.css frontend/components/chat/MessageInput.tsx frontend/components/chat/MessageInput.module.css
git commit -m "feat(frontend): Atelier sidebar rail and message input"
```

---

### Task 4: The dialogue — prose-only bubbles + thinking lamp

**Files:**
- Modify: `frontend/components/chat/MessageBubble.tsx` (full rewrite)
- Create: `frontend/components/chat/MessageBubble.module.css`
- Modify: `frontend/components/chat/MessageList.tsx` (full rewrite)
- Create: `frontend/components/chat/MessageList.module.css`
- Create: `frontend/components/chat/toolNames.ts`

**Interfaces:**
- Consumes: `splitMessageContent`, `renderInlineMarkdown`, types from Task 2.
- Produces (Task 6 wires these):

```ts
// MessageBubble
export interface MessageBubbleProps {
  role: string;
  content: string;              // prose-only content (tables already stripped by caller)
  hasTables: boolean;           // show "on the desk →" affordance
  onShowArtifact?: (() => void) | undefined;
}
// MessageList
export interface DisplayMessage {
  role: string;
  content: string;
  requestId?: string | undefined;
}
export interface MessageListProps {
  messages: DisplayMessage[];
  thinkingTool: string | null;                       // business phrase or null
  onShowArtifact: (messageIndex: number) => void;
}
// toolNames.ts
export function toolDisplayName(tool: string): string;
```

- [ ] **Step 1: Create `toolNames.ts`** (presentation map; unknown tools fall back to "the ledgers")

```ts
const TOOL_PHRASES: Record<string, string> = {
  get_unpaid_invoices: "unpaid invoices",
  get_overdue_invoices: "overdue invoices",
  search_invoices: "invoice search",
  get_customer_balance: "customer balances",
  get_vendor_balance: "vendor balances",
  get_vendor_invoices: "vendor invoices",
  get_customer: "customer records",
  search_customers: "customer search",
  get_aging_report: "the aging report",
  find_duplicate_invoices: "the duplicate check",
  get_cash_position: "the cash ledger",
  get_current_date: "the calendar",
};

export function toolDisplayName(tool: string): string {
  return TOOL_PHRASES[tool] ?? "the ledgers";
}
```

- [ ] **Step 2: Rewrite `MessageBubble.tsx`** (prose-only; no TracePanel import — the trace moves to the drawer in Task 5)

```tsx
"use client";

import { renderInlineMarkdown } from "./markdown";
import styles from "./MessageBubble.module.css";

export interface MessageBubbleProps {
  role: string;
  content: string;
  hasTables: boolean;
  onShowArtifact?: (() => void) | undefined;
}

export function MessageBubble({ role, content, hasTables, onShowArtifact }: MessageBubbleProps) {
  if (role === "user") {
    return (
      <div className={styles.userRow}>
        <span className={styles.userCard}>{content}</span>
      </div>
    );
  }

  return (
    <div className={styles.assistant}>
      <span
        className={styles.prose}
        dangerouslySetInnerHTML={{ __html: renderInlineMarkdown(content) }}
      />
      {hasTables && onShowArtifact && (
        <button type="button" className={styles.deskLink} onClick={onShowArtifact}>
          on the desk →
        </button>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Create `MessageBubble.module.css`**

```css
.userRow {
  display: flex;
  justify-content: flex-end;
  margin: 1.1rem 0;
  animation: rise 150ms ease-out;
}

.userCard {
  background: var(--surface-raised);
  border-radius: 10px 10px 2px 10px;
  box-shadow: var(--shadow-card);
  color: var(--ink);
  font-family: var(--sans);
  font-size: 0.92rem;
  line-height: 1.45;
  max-width: 70%;
  padding: 0.55rem 0.9rem;
}

.assistant {
  margin: 1.1rem 0;
  animation: rise 150ms ease-out;
}

.prose {
  display: block;
  color: var(--ink);
  font-family: var(--serif);
  font-size: 1.02rem;
  line-height: 1.65;
  max-width: 65ch;
}

.prose code {
  font-family: var(--mono);
  font-size: 0.88em;
  color: var(--ink-soft);
}

.prose strong {
  color: var(--ink-soft);
}

.deskLink {
  display: inline-block;
  background: transparent;
  border: none;
  color: var(--brass);
  cursor: pointer;
  font-family: var(--sans);
  font-size: 0.78rem;
  letter-spacing: 0.04em;
  margin-top: 0.4rem;
  padding: 0;
  transition: opacity 120ms ease;
}

.deskLink:hover {
  opacity: 0.8;
}

@keyframes rise {
  from {
    opacity: 0;
    transform: translateY(4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
```

- [ ] **Step 4: Rewrite `MessageList.tsx`** (splits each assistant message; renders the thinking lamp while a tool runs)

```tsx
import { splitMessageContent } from "./markdown";
import { MessageBubble } from "./MessageBubble";
import styles from "./MessageList.module.css";

export interface DisplayMessage {
  role: string;
  content: string;
  requestId?: string | undefined;
}

export interface MessageListProps {
  messages: DisplayMessage[];
  thinkingTool: string | null;
  onShowArtifact: (messageIndex: number) => void;
}

export function MessageList({ messages, thinkingTool, onShowArtifact }: MessageListProps) {
  return (
    <div>
      {messages.map((message, index) => {
        if (message.role !== "assistant") {
          return (
            <MessageBubble key={index} role={message.role} content={message.content} hasTables={false} />
          );
        }
        const segments = splitMessageContent(message.content);
        const prose = segments
          .filter((s) => s.kind === "prose")
          .map((s) => s.text)
          .join("\n\n");
        const hasTables = segments.some((s) => s.kind === "table");
        if (prose === "" && !hasTables) {
          return null;
        }
        return (
          <MessageBubble
            key={index}
            role="assistant"
            content={prose}
            hasTables={hasTables}
            onShowArtifact={hasTables ? () => onShowArtifact(index) : undefined}
          />
        );
      })}
      {thinkingTool !== null && (
        <div className={styles.thinking} role="status">
          <span className={styles.lampDot} aria-hidden="true" />
          <span className={styles.thinkingText}>Consulting the ledgers — {thinkingTool}…</span>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Create `MessageList.module.css`**

```css
.thinking {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin: 1rem 0;
}

.lampDot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--brass);
  animation: pulse 1.4s ease-in-out infinite;
}

.thinkingText {
  color: var(--pencil);
  font-family: var(--serif);
  font-size: 0.9rem;
  font-style: italic;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 0.5;
    box-shadow: 0 0 2px var(--brass);
  }
  50% {
    opacity: 1;
    box-shadow: 0 0 10px var(--brass);
  }
}
```

- [ ] **Step 6: Temporary wiring so the app compiles** — in `app/page.tsx`, update the `MessageList` usage to `messages={messages} thinkingTool={null} onShowArtifact={() => {}}` and remove the `tool_call` content replacement (delete the `else if (event.type === "tool_call") {...}` branch body's `setMessages` call, leaving the branch empty for Task 6 — or simply `// wired in drawer task`). Full drawer wiring replaces this in Task 6.

- [ ] **Step 7: Verify**

Run: `cd frontend && npm run lint && npm run typecheck && npm run build`
Expected: clean. Dev-run: assistant prose renders in Fraunces without bubbles, tables no longer appear in chat (they'll reappear in the drawer in Tasks 5–6), user messages are right-aligned cards.

- [ ] **Step 8: Commit**

```bash
git add frontend/components/chat/MessageBubble.tsx frontend/components/chat/MessageBubble.module.css frontend/components/chat/MessageList.tsx frontend/components/chat/MessageList.module.css frontend/components/chat/toolNames.ts frontend/app/page.tsx
git commit -m "feat(frontend): serif dialogue, prose-only bubbles, thinking lamp"
```

---

### Task 5: The desk — ResultTable, ResultDrawer, restyled TracePanel

**Files:**
- Create: `frontend/components/chat/ResultTable.tsx`
- Create: `frontend/components/chat/ResultTable.module.css`
- Create: `frontend/components/chat/ResultDrawer.tsx`
- Create: `frontend/components/chat/ResultDrawer.module.css`
- Modify: `frontend/components/chat/TracePanel.tsx` (styling swap only: replace every inline `style={{...}}` with classes)
- Create: `frontend/components/chat/TracePanel.module.css`

**Interfaces:**
- Consumes: `TableSegment` from `./markdown` (Task 2); `renderInlineSpan`-safe cell text is plain strings (cells are rendered as text, not HTML — table cells never carried markdown that matters, and plain text is XSS-safe by construction).
- Produces (Task 6 wires these):

```ts
export interface ResultArtifact {
  messageIndex: number;
  requestId?: string | undefined;
  title: string;
  tables: TableSegment[];
  rowCount: number;
}
export type DrawerTab = "result" | "trace";
export interface ResultDrawerProps {
  artifact: ResultArtifact;
  tab: DrawerTab;
  pinned: boolean;
  onTabChange: (tab: DrawerTab) => void;
  onTogglePin: () => void;
  onDismiss: () => void;
}
// ResultTable
export interface ResultTableProps {
  table: TableSegment;
}
```

- [ ] **Step 1: Create `ResultTable.tsx`** (presentational numeric/status detection per spec: a column is numeric when >50% of body cells parse as numbers/currency; /days/i header + positive number → ember; status cell `paid` → sage, `overdue` → ember)

```tsx
import type { TableSegment } from "./markdown";
import styles from "./ResultTable.module.css";

export interface ResultTableProps {
  table: TableSegment;
}

function parseNumeric(cell: string): number | null {
  const cleaned = cell.replace(/[$,\s]/g, "");
  if (cleaned === "" || !/^-?\d+(\.\d+)?$/.test(cleaned)) {
    return null;
  }
  return Number(cleaned);
}

function numericColumns(table: TableSegment): boolean[] {
  return table.headerCells.map((_, col) => {
    const cells = table.bodyRows.map((row) => row[col] ?? "");
    const nonEmpty = cells.filter((c) => c.trim() !== "");
    if (nonEmpty.length === 0) {
      return false;
    }
    const numeric = nonEmpty.filter((c) => parseNumeric(c) !== null);
    return numeric.length / nonEmpty.length > 0.5;
  });
}

function cellClass(header: string, cell: string, isNumeric: boolean): string {
  const value = cell.trim().toLowerCase();
  if (/status/i.test(header)) {
    if (value === "paid") {
      return `${styles.cell} ${styles.sage}`;
    }
    if (value === "overdue") {
      return `${styles.cell} ${styles.ember}`;
    }
  }
  if (/days/i.test(header)) {
    const n = parseNumeric(cell);
    if (n !== null && n > 0) {
      return `${styles.cell} ${styles.numeric} ${styles.ember}`;
    }
  }
  return isNumeric ? `${styles.cell} ${styles.numeric}` : styles.cell;
}

export function ResultTable({ table }: ResultTableProps) {
  const numeric = numericColumns(table);
  return (
    <div className={styles.card}>
      <table className={styles.table}>
        <thead>
          <tr>
            {table.headerCells.map((cell, i) => (
              <th key={i} className={numeric[i] ? `${styles.header} ${styles.numeric}` : styles.header}>
                {cell}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {table.bodyRows.map((row, r) => (
            <tr key={r} className={styles.row}>
              {row.map((cell, c) => (
                <td key={c} className={cellClass(table.headerCells[c] ?? "", cell, numeric[c] ?? false)}>
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 2: Create `ResultTable.module.css`**

```css
.card {
  background: var(--surface);
  border: 1px solid var(--seam);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
  margin-bottom: 0.75rem;
  overflow-x: auto;
  padding: 0.4rem;
}

.table {
  border-collapse: collapse;
  width: 100%;
  font-size: 0.82rem;
}

.header {
  color: var(--pencil);
  font-family: var(--sans);
  font-size: 0.7rem;
  font-weight: 500;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  text-align: left;
  padding: 0.35rem 0.5rem;
}

.row {
  border-top: 1px solid var(--seam);
}

.cell {
  color: var(--ink);
  font-family: var(--sans);
  padding: 0.35rem 0.5rem;
  text-align: left;
  white-space: nowrap;
}

.numeric {
  font-family: var(--mono);
  font-variant-numeric: tabular-nums;
  text-align: right;
}

.ember {
  color: var(--ember);
}

.sage {
  color: var(--sage);
}
```

- [ ] **Step 3: Create `ResultDrawer.tsx`** (Esc dismisses; `role="complementary"`)

```tsx
"use client";

import { useEffect } from "react";

import type { TableSegment } from "./markdown";
import { ResultTable } from "./ResultTable";
import { TracePanel } from "./TracePanel";
import styles from "./ResultDrawer.module.css";

export interface ResultArtifact {
  messageIndex: number;
  requestId?: string | undefined;
  title: string;
  tables: TableSegment[];
  rowCount: number;
}

export type DrawerTab = "result" | "trace";

export interface ResultDrawerProps {
  artifact: ResultArtifact;
  tab: DrawerTab;
  pinned: boolean;
  onTabChange: (tab: DrawerTab) => void;
  onTogglePin: () => void;
  onDismiss: () => void;
}

export function ResultDrawer({
  artifact,
  tab,
  pinned,
  onTabChange,
  onTogglePin,
  onDismiss,
}: ResultDrawerProps) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onDismiss();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onDismiss]);

  return (
    <aside className={styles.drawer} role="complementary" aria-label={artifact.title}>
      <div className={styles.bar} role="tablist">
        <button
          role="tab"
          aria-selected={tab === "result"}
          className={tab === "result" ? styles.tabActive : styles.tab}
          onClick={() => onTabChange("result")}
        >
          Result
        </button>
        {artifact.requestId && (
          <button
            role="tab"
            aria-selected={tab === "trace"}
            className={tab === "trace" ? styles.tabActive : styles.tab}
            onClick={() => onTabChange("trace")}
          >
            Trace
          </button>
        )}
        <span className={styles.spacer} />
        <button
          className={pinned ? styles.pinActive : styles.pin}
          aria-pressed={pinned}
          onClick={onTogglePin}
          title={pinned ? "Unpin" : "Pin this result"}
        >
          ⊙
        </button>
        <button className={styles.close} onClick={onDismiss} aria-label="Dismiss drawer">
          ✕
        </button>
      </div>
      <div className={styles.header}>
        {artifact.title} — {artifact.rowCount} {artifact.rowCount === 1 ? "row" : "rows"}
      </div>
      <div className={styles.body}>
        {tab === "result" &&
          artifact.tables.map((table, i) => <ResultTable key={i} table={table} />)}
        {tab === "trace" && artifact.requestId && <TracePanel requestId={artifact.requestId} />}
      </div>
    </aside>
  );
}
```

- [ ] **Step 4: Create `ResultDrawer.module.css`**

```css
.drawer {
  width: min(440px, 42vw);
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: #1b1510;
  border-left: 1px solid var(--seam-strong);
  box-shadow: var(--shadow-drawer);
  padding: 0.9rem;
  animation: slideIn 280ms ease-out;
}

.bar {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.tab,
.tabActive {
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--pencil-faint);
  cursor: pointer;
  font-family: var(--sans);
  font-size: 0.72rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  padding: 0.2rem 0;
  transition: color 120ms ease, border-color 120ms ease;
}

.tabActive {
  color: var(--ink);
  border-bottom-color: var(--brass);
}

.tab:hover {
  color: var(--ink-soft);
}

.spacer {
  flex: 1;
}

.pin,
.pinActive,
.close {
  background: transparent;
  border: none;
  cursor: pointer;
  font-size: 0.9rem;
  padding: 0.1rem 0.25rem;
  transition: color 120ms ease;
}

.pin {
  color: var(--pencil-faint);
}

.pinActive {
  color: var(--brass);
}

.close {
  color: var(--pencil-faint);
}

.close:hover,
.pin:hover {
  color: var(--ink-soft);
}

.header {
  color: var(--pencil);
  font-family: var(--sans);
  font-size: 0.8rem;
  margin: 0.6rem 0;
}

.body {
  flex: 1;
  overflow-y: auto;
}

@keyframes slideIn {
  from {
    transform: translateX(24px);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}
```

- [ ] **Step 5: Restyle `TracePanel.tsx`** — keep all logic and JSX structure; replace every inline `style` with classes and delete the `style` props. The mapping:
  - error `<p>` → `className={styles.error}` (ember text, 0.85rem)
  - loading `<p>` → `className={styles.loading}` (pencil, italic)
  - container `<div>` → `className={styles.panel}`
  - each row `<div>` → `className={styles.line}` with `<strong>` styled by `.line strong`
  - table → `className={styles.traceTable}`, `th` → `.traceHeader`, no inline padding

Create `TracePanel.module.css`:

```css
.error {
  color: var(--ember);
  font-size: 0.85rem;
}

.loading {
  color: var(--pencil);
  font-size: 0.85rem;
  font-style: italic;
}

.panel {
  background: var(--surface);
  border: 1px solid var(--seam);
  border-radius: var(--radius-card);
  font-family: var(--mono);
  font-size: 0.78rem;
  padding: 0.75rem;
}

.line {
  color: var(--ink);
  margin-bottom: 0.35rem;
}

.line strong {
  color: var(--pencil);
  font-family: var(--sans);
  font-size: 0.68rem;
  font-weight: 500;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-right: 0.35rem;
}

.traceTable {
  border-collapse: collapse;
  margin-top: 0.5rem;
  width: 100%;
}

.traceTable th {
  color: var(--pencil);
  font-family: var(--sans);
  font-size: 0.68rem;
  font-weight: 500;
  letter-spacing: 0.08em;
  text-align: left;
  text-transform: uppercase;
  padding: 0.2rem 0.5rem 0.2rem 0;
}

.traceTable td {
  color: var(--ink);
  padding: 0.2rem 0.5rem 0.2rem 0;
}
```

- [ ] **Step 6: Verify**

Run: `cd frontend && npm run lint && npm run typecheck && npm run build`
Expected: clean (the new components are not yet imported by the page — Next still compiles them; `npm run lint` covers them).

- [ ] **Step 7: Commit**

```bash
git add frontend/components/chat/ResultTable.tsx frontend/components/chat/ResultTable.module.css frontend/components/chat/ResultDrawer.tsx frontend/components/chat/ResultDrawer.module.css frontend/components/chat/TracePanel.tsx frontend/components/chat/TracePanel.module.css
git commit -m "feat(frontend): result drawer with ledger tables and trace tab"
```

---

### Task 6: Wiring the workspace — drawer state, first light, thinking state

**Files:**
- Create: `frontend/components/chat/EmptyState.tsx`
- Create: `frontend/components/chat/EmptyState.module.css`
- Modify: `frontend/app/page.tsx` (full rewrite below)
- Modify: `frontend/app/page.module.css` (append)

**Interfaces:**
- Consumes: everything from Tasks 2–5 exactly as typed there.
- Produces: the finished workspace.

- [ ] **Step 1: Create `EmptyState.tsx`**

```tsx
import styles from "./EmptyState.module.css";

export interface EmptyStateProps {
  onPick: (question: string) => void;
  disabled: boolean;
}

const SUGGESTIONS = [
  "Who hasn't paid us?",
  "Generate an aging report",
  "Find duplicate invoices",
];

function greeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) {
    return "Good morning. The books are open.";
  }
  if (hour < 18) {
    return "Good afternoon. The books are open.";
  }
  return "Good evening. The books are open.";
}

export function EmptyState({ onPick, disabled }: EmptyStateProps) {
  return (
    <div className={styles.room}>
      <div className={styles.kicker}>Northwind Manufacturing · Finance</div>
      <h1 className={styles.greeting}>{greeting()}</h1>
      <div className={styles.chips}>
        {SUGGESTIONS.map((question) => (
          <button
            key={question}
            className={styles.chip}
            onClick={() => onPick(question)}
            disabled={disabled}
          >
            {question}
          </button>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create `EmptyState.module.css`**

```css
.room {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  text-align: center;
}

.kicker {
  color: var(--pencil);
  font-family: var(--sans);
  font-size: 0.68rem;
  letter-spacing: 0.25em;
  text-transform: uppercase;
}

.greeting {
  color: var(--ink);
  font-family: var(--serif);
  font-size: 1.9rem;
  font-weight: 400;
  margin: 0.9rem 0 0.4rem;
}

.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
  justify-content: center;
  margin-top: 1.4rem;
}

.chip {
  background: transparent;
  border: 1px solid var(--seam-strong);
  border-radius: var(--radius-chip);
  color: var(--ink-soft);
  cursor: pointer;
  font-family: var(--sans);
  font-size: 0.85rem;
  padding: 0.45rem 1rem;
  transition: border-color 120ms ease, color 120ms ease;
}

.chip:hover:not(:disabled) {
  border-color: var(--brass);
  color: var(--brass);
}

.chip:disabled {
  opacity: 0.5;
  cursor: default;
}
```

- [ ] **Step 3: Rewrite `app/page.tsx`** (complete file — drawer state machine per spec: unpinned follows newest artifact; pin freezes; "on the desk →" opens that artifact and clears the pin; drawer closed by default when switching conversations; `tool_call` drives the thinking lamp instead of replacing content)

```tsx
"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  getConversationMessages,
  getSessionId,
  listConversations,
  streamChat,
  type ConversationSummary,
} from "@/lib/api-client";
import { ConversationSidebar } from "@/components/chat/ConversationSidebar";
import { EmptyState } from "@/components/chat/EmptyState";
import { MessageInput } from "@/components/chat/MessageInput";
import { MessageList, type DisplayMessage } from "@/components/chat/MessageList";
import {
  ResultDrawer,
  type DrawerTab,
  type ResultArtifact,
} from "@/components/chat/ResultDrawer";
import { deriveArtifactTitle, splitMessageContent } from "@/components/chat/markdown";
import { toolDisplayName } from "@/components/chat/toolNames";
import styles from "./page.module.css";

function buildArtifacts(messages: DisplayMessage[]): ResultArtifact[] {
  const artifacts: ResultArtifact[] = [];
  messages.forEach((message, index) => {
    if (message.role !== "assistant") {
      return;
    }
    const segments = splitMessageContent(message.content);
    const tables = segments.filter((s) => s.kind === "table");
    if (tables.length === 0) {
      return;
    }
    artifacts.push({
      messageIndex: index,
      requestId: message.requestId,
      title: deriveArtifactTitle(segments),
      tables,
      rowCount: tables.reduce((sum, t) => sum + t.bodyRows.length, 0),
    });
  });
  return artifacts;
}

export default function HomePage() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [thinkingTool, setThinkingTool] = useState<string | null>(null);

  const [drawerIndex, setDrawerIndex] = useState<number | null>(null);
  const [drawerPinned, setDrawerPinned] = useState(false);
  const [drawerTab, setDrawerTab] = useState<DrawerTab>("result");

  const artifacts = useMemo(() => buildArtifacts(messages), [messages]);
  const latestArtifact = artifacts.length > 0 ? artifacts[artifacts.length - 1]! : null;
  const openArtifact =
    drawerIndex !== null
      ? (artifacts.find((a) => a.messageIndex === drawerIndex) ?? null)
      : null;

  // Unpinned drawer follows the newest artifact as it arrives.
  useEffect(() => {
    if (!drawerPinned && latestArtifact && !isStreaming) {
      setDrawerIndex(latestArtifact.messageIndex);
      setDrawerTab("result");
    }
  }, [latestArtifact, drawerPinned, isStreaming]);

  useEffect(() => {
    setSessionId(getSessionId());
  }, []);

  useEffect(() => {
    if (!sessionId) {
      return;
    }
    listConversations(sessionId)
      .then(setConversations)
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Could not load conversations.");
      });
  }, [sessionId]);

  const closeDrawer = useCallback(() => {
    setDrawerIndex(null);
    setDrawerPinned(false);
  }, []);

  const handleShowArtifact = useCallback((messageIndex: number) => {
    // An explicit click wins: open that artifact and clear any pin (spec).
    setDrawerIndex(messageIndex);
    setDrawerPinned(false);
    setDrawerTab("result");
  }, []);

  const handleSelectConversation = useCallback(
    (conversationId: string) => {
      setActiveConversationId(conversationId);
      setError(null);
      closeDrawer();
      getConversationMessages(conversationId)
        .then((history) =>
          setMessages(history.map((m) => ({ role: m.role, content: m.content }))),
        )
        .catch((err: unknown) => {
          setError(err instanceof Error ? err.message : "Could not load messages.");
        });
    },
    [closeDrawer],
  );

  const handleNewConversation = useCallback(() => {
    setActiveConversationId(null);
    setMessages([]);
    setError(null);
    closeDrawer();
  }, [closeDrawer]);

  const handleSend = useCallback(
    async (message: string) => {
      if (!sessionId) {
        return;
      }
      setError(null);
      setMessages((prev) => [...prev, { role: "user", content: message }]);
      setIsStreaming(true);

      let assistantContent = "";
      let requestId: string | undefined;
      setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

      try {
        for await (const event of streamChat(sessionId, message, activeConversationId)) {
          if (event.type === "request_id") {
            requestId = event.request_id;
            setMessages((prev) => [
              ...prev.slice(0, -1),
              { role: "assistant", content: assistantContent, requestId },
            ]);
          } else if (event.type === "tool_call") {
            setThinkingTool(toolDisplayName(event.tool));
          } else if (event.type === "token") {
            setThinkingTool(null);
            assistantContent += event.content;
            setMessages((prev) => [
              ...prev.slice(0, -1),
              { role: "assistant", content: assistantContent, requestId },
            ]);
          } else if (event.type === "done") {
            setActiveConversationId(event.conversation_id);
            const updated = await listConversations(sessionId);
            setConversations(updated);
          } else if (event.type === "error") {
            setError(event.message);
            setMessages((prev) => {
              const last = prev[prev.length - 1];
              if (last && last.role === "assistant" && assistantContent === "") {
                return prev.slice(0, -1);
              }
              return prev;
            });
          }
        }
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Something went wrong. Please try again.");
      } finally {
        setIsStreaming(false);
        setThinkingTool(null);
      }
    },
    [sessionId, activeConversationId],
  );

  const showEmptyState = messages.length === 0;

  return (
    <main className={styles.workspace}>
      <ConversationSidebar
        conversations={conversations}
        activeConversationId={activeConversationId}
        onSelect={handleSelectConversation}
        onNewConversation={handleNewConversation}
        disabled={isStreaming}
      />
      <section className={styles.dialogue}>
        {showEmptyState ? (
          <EmptyState onPick={handleSend} disabled={isStreaming || !sessionId} />
        ) : (
          <div className={styles.scroll}>
            <MessageList
              messages={messages}
              thinkingTool={thinkingTool}
              onShowArtifact={handleShowArtifact}
            />
          </div>
        )}
        {error && <p className={styles.errorCard} role="alert">{error}</p>}
        <MessageInput disabled={isStreaming || !sessionId} onSend={handleSend} />
      </section>
      {openArtifact && (
        <ResultDrawer
          artifact={openArtifact}
          tab={drawerTab}
          pinned={drawerPinned}
          onTabChange={setDrawerTab}
          onTogglePin={() => setDrawerPinned((p) => !p)}
          onDismiss={closeDrawer}
        />
      )}
    </main>
  );
}
```

- [ ] **Step 4: Verify**

Run: `cd frontend && npm run lint && npm run typecheck && npm run build`
Expected: clean.

- [ ] **Step 5: Live behavior check** (backend running + seeded; from `backend/`: `.venv/Scripts/python -m uvicorn app.main:app`)

Dev-run the frontend and verify by hand:
- First light: kicker, greeting, three chips; clicking "Who hasn't paid us?" sends it.
- Thinking lamp shows "Consulting the ledgers — unpaid invoices…" during the turn.
- Answer: prose in serif; table appears in the drawer with "… — N rows" header; bubble shows "on the desk →".
- TRACE tab shows plan branch/prompt versions/durations.
- Pin the drawer, ask "Generate an aging report" — drawer stays; unpin — it jumps to the aging artifact.
- Esc dismisses. Switching conversations closes the drawer.

- [ ] **Step 6: Commit**

```bash
git add frontend/components/chat/EmptyState.tsx frontend/components/chat/EmptyState.module.css frontend/app/page.tsx frontend/app/page.module.css
git commit -m "feat(frontend): wire the workspace - drawer state, first light, thinking lamp"
```

---

### Task 7: Final verification + docs

**Files:**
- Modify: `frontend/README.md` (describe the Atelier design + drawer)

**Interfaces:**
- Consumes: the finished app.

- [ ] **Step 1: Full check suite**

```bash
cd frontend && npm run lint && npm run typecheck && npm run build
```
Expected: all clean.

- [ ] **Step 2: Playwright walkthrough per the spec's Verification section** (backend seeded + running, `npm run dev` running; use the Playwright MCP browser tools)

Walk: first light renders → chip sends → unpaid-invoices drawer (title + row count) → TRACE tab content → pin across a second question → unpin jump → "Delete all invoices" refusal renders as plain prose with **no drawer** → Esc dismisses → screenshot the workspace with the drawer open for the record. Reduced-motion spot check: emulate `prefers-reduced-motion` and confirm no slide/pulse animation.

- [ ] **Step 3: Update `frontend/README.md`** — replace the second paragraph (the one describing the home page) with:

```markdown
The home page is "The Atelier": a dark, lamp-lit workspace. Assistant prose
renders in a serif voice directly on the wall; any reply containing tables
sends them to a right-side result drawer (RESULT/TRACE tabs, pin, Esc to
dismiss) so data gets room while the dialogue stays readable. While tools
run, a brass lamp pulses ("Consulting the ledgers — …"). Design tokens live
in `app/globals.css`; each component has a co-located CSS Module; fonts
(Fraunces + JetBrains Mono) load via `next/font`. All backend communication
goes through `lib/api-client.ts`, a typed fetch wrapper. `npm run lint`,
`npm run typecheck`, and `npm run build` are the CI checks.
```

- [ ] **Step 4: Verify backend untouched**

```bash
cd "D:\New-Automation\AI-FinanceAssistant" && git status --short backend/ ai_platform/ domains/ | grep -v "^??" || echo "backend untouched"
```
Expected: `backend untouched`.

- [ ] **Step 5: Commit**

```bash
git add frontend/README.md
git commit -m "docs(frontend): describe the Atelier design"
```

Then use the superpowers:finishing-a-development-branch skill (merge/PR decision with the user).

---

## Self-Review (completed at planning time)

- **Spec coverage:** tokens/typography/motion → Task 1 + component modules; three moments → EmptyState (T6), thinking lamp (T4+T6), drawer (T5+T6); prose-only bubbles + affordance → T4; splitter + title derivation → T2; numeric/status coloring rules → T5 Step 1 exactly as spec'd; accessibility (focus rings T1, drawer roles/Esc/aria T5, reduced-motion T1); error card → T1/T6; verification section → T6 Step 5 + T7 Step 2. Out-of-scope items: none implemented (no stats endpoint, no theme toggle, no test runner, no api-client change — enforced by T7 Step 4).
- **Placeholder scan:** none; every code step is complete file/fragment content.
- **Type consistency:** `MessageSegment/TableSegment` (T2) consumed by T4 `MessageList`, T5 `ResultTable/ResultArtifact`, T6 `buildArtifacts`; `DrawerTab`, `ResultDrawerProps` match between T5 definition and T6 usage; `MessageListProps.onShowArtifact(messageIndex: number)` matches T6's handler; `toolDisplayName` (T4) used in T6's `tool_call` branch. `MessageBubbleProps.onShowArtifact?: (() => void) | undefined` matches the conditional spread-free usage in T4 Step 4.
- **Known sequencing note:** Task 4 Step 6 leaves `page.tsx` with temporary `thinkingTool={null}` wiring so every task compiles independently; Task 6 replaces the file wholesale.
