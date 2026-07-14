# The Atelier — Frontend Redesign Design

Date: 2026-07-14 · Status: approved by user (brainstorming session with visual
companion; direction, layout, and both design sections approved)

## Purpose

Replace the visually bare frontend (32 lines of CSS, system font, inline
styles) with a distinctive, immersive design — explicitly **not** the generic
"AI product" look (no purple, no gradient-on-black slop). The backend, API
client contract, and all business behavior are untouched: this is a
presentation-layer redesign of the existing, working chat application.

## Design language — "The Atelier"

A lamp-lit study for the company's books. Warm, tactile, quiet authority.

### Color tokens (CSS custom properties in `globals.css`)

| Token | Value | Role |
|---|---|---|
| `--room` | `#15110D` | page background (deepest) |
| `--wall` | `#1E1813` | chat/workspace background |
| `--surface` | `#211A14` | cards, tables, input, drawer panels |
| `--surface-raised` | `#241D16` | active sidebar item, hover states |
| `--seam` | `#2C241C` | hairline borders |
| `--seam-strong` | `#3A2E22` | drawer edge, emphasized borders |
| `--ink` | `#E8DFD3` | primary text |
| `--ink-soft` | `#D9C9A8` | secondary emphasis (figures, active labels) |
| `--pencil` | `#8A7A65` | muted labels, metadata |
| `--pencil-faint` | `#6E5F4E` | faintest text (hints, timestamps) |
| `--brass` | `#C98A3D` | THE interactive accent: focus, links, active tab, lamp, pin |
| `--ember` | `#C96F3D` | overdue/risk figures ONLY |
| `--sage` | `#7FA07C` | paid/healthy figures ONLY |

Rules: brass is the only interactive accent; ember and sage are semantic
(risk/health) and never decorative. A faint radial vignette on the workspace
(`radial-gradient` from `#241C15` toward `--room`) gives the room its lamp.
No purple anywhere.

### Typography

- **Fraunces** (via `next/font/google`, self-hosted at build time; fallback
  Georgia/serif) — headings, the assistant's prose, the empty-state greeting.
  This serif voice is the single biggest "not AI slop" move.
- **System sans** (existing stack) — UI chrome: sidebar, labels, buttons,
  user messages.
- **JetBrains Mono** (via `next/font/google`; fallback monospace), with
  `font-variant-numeric: tabular-nums` — every figure, invoice number,
  bucket, and trace value. Money aligns like a ledger.

### Motion (CSS-only, all behind `prefers-reduced-motion`)

- Drawer slides in from the right (~280ms ease-out); chat column compresses
  via the grid transition.
- Thinking state: a single brass lamp dot pulses (opacity/glow keyframes).
- Message entry: subtle fade/rise (~150ms). Hover/focus transitions ~120ms.
- No parallax, no ambient animation, no spring libraries.

## The experience — three moments

1. **First light (empty state).** Instead of a blank chat: a centered
   greeting in Fraunces — time-of-day aware ("Good morning/afternoon/
   evening. The books are open.") — over the vignette, with an uppercase
   letterspaced kicker ("Northwind Manufacturing · Finance") and three
   suggestion chips of real capabilities ("Who hasn't paid us?", "Generate
   an aging report", "Find duplicate invoices"). Clicking a chip sends it as
   a message. **No live figures** — that would need a new backend endpoint;
   out of scope.
2. **Thinking.** While tools run (existing `tool_call` SSE events), an
   italic pencil-toned line with the pulsing brass lamp: "Consulting the
   ledgers — aging report…". Tool names are rendered as business phrases via
   a small display-name map (e.g. `get_aging_report` → "aging report");
   unknown tools fall back to a generic "the ledgers". Internals are never
   shown.
3. **The drawer (summoned canvas).** Prose lives in the dialogue; data lives
   on the desk. When an assistant message contains markdown table(s), the
   tables render in a right-side drawer, not in the bubble. The drawer has
   RESULT and TRACE tabs, a pin toggle, a dismiss (✕ / Esc), and a header
   line ("Unpaid invoices — 87 rows" derived from the table itself: row
   count + nearest preceding heading or first prose line, else
   "Result"). Unpinned, it always shows the latest artifact; pinned, it
   stays put until unpinned or dismissed. Each table-bearing bubble shows a
   quiet "on the desk →" affordance; clicking it opens the drawer on that
   message's artifact (clearing any pin — an explicit click wins).

Message bubbles: user messages are compact sans cards, right-aligned, with
an asymmetric radius (10px / 10px / 2px / 10px). Assistant prose is
bubble-less — set directly on the wall in Fraunces at a readable measure
(~65ch max), like a letter, separated by generous whitespace.

Error events (existing `error` SSE type): a quiet surface card with an
ember left border — friendly text only (backend already guarantees this).

## Architecture

### What does NOT change

- `lib/api-client.ts` — zero changes; all SSE events and endpoints as-is.
- Backend — zero changes.
- All existing behavior: streaming, conversation list/switch, trace fetch.

### Files

| File | Change |
|---|---|
| `app/layout.tsx` | wire `next/font` (Fraunces, JetBrains Mono), font CSS variables |
| `app/globals.css` | design tokens, base type, vignette, reduced-motion guards |
| `app/page.tsx` | workspace grid (sidebar / dialogue / drawer), drawer state `{artifact, pinned, tab}`, empty-state branch |
| `components/chat/markdown.ts` | add pure `splitMessageContent(content) → {segments: (prose | table)[]}` splitter for markdown table blocks (string parsing only — no business rules); existing inline renderer stays for prose |
| `components/chat/MessageBubble.tsx` | prose-only rendering; "on the desk →" affordance when the message had tables; drop inline TracePanel |
| `components/chat/MessageList.tsx` | thinking-lamp state, entry motion, spacing |
| `components/chat/MessageInput.tsx` | "Ask the books anything…" input styling, brass submit |
| `components/chat/ConversationSidebar.tsx` | Atelier rail styling, active state, "+ New conversation" |
| `components/chat/TracePanel.tsx` | restyled as the drawer's TRACE tab (same `getTrace` call) |
| `components/chat/ResultDrawer.tsx` | **new** — drawer shell: tabs, pin, dismiss, Esc, `role="complementary"`, slide transition |
| `components/chat/ResultTable.tsx` | **new** — ledger table renderer from split table markdown: mono figures, right-aligned numeric columns, ember on overdue "days" values, sage on `paid` status |
| `components/chat/EmptyState.tsx` | **new** — first light |
| Per-component `*.module.css` | co-located CSS Modules (Next 15 built-in; no new dependencies) |

### Data flow for the drawer

`streamChat` completes an assistant message → `page.tsx` runs
`splitMessageContent` → prose segments go to the bubble; if table segments
exist, they become the message's artifact `{requestId, title, tables}` →
drawer state updates to the newest artifact unless pinned. Selecting an old
conversation rebuilds artifacts the same way from loaded history (latest
one shown, drawer closed by default when opening a conversation). The TRACE
tab lazy-fetches via the existing `getTrace(requestId)` on first open, as
today.

Numeric-column detection in `ResultTable` is presentational: a column is
right-aligned mono when >50% of its body cells parse as
number/currency-formatted strings. "Days" cells render ember when the
column header matches /days/i and the value is a positive number; a
`status` cell renders sage when the value is `paid`, ember when `overdue`.
This styles what the backend already said — it decides nothing.

## Accessibility

- Brass `:focus-visible` rings on all interactive elements.
- Drawer: `role="complementary"`, labelled by its header; Esc dismisses;
  pin/dismiss/tabs are buttons with `aria-pressed`/`aria-selected`.
- Contrast: `--ink` on `--wall` ≈ 12:1; `--pencil` reserved for
  non-essential text; ember/sage figures always ≥4.5:1 on their surfaces.
- `prefers-reduced-motion: reduce` disables slide/pulse/rise animations.

## Out of scope (explicitly)

- Live figures in the empty state (needs a backend stats endpoint).
- Light mode / theme toggle (dark-first single mode, per user decision).
- Frontend test runner (none exists across Milestones 1–10; not added for a
  visual change).
- Any backend, API-client, or business-logic change.
- Charts beyond the aging distribution bar already shown in tables (CSS
  proportional bar under the aging table is included; real charting is not).

## Verification

- `npm run lint`, `npm run typecheck`, `npm run build` — clean.
- Live Playwright walkthrough against the running app (seed=42): first
  light renders with chips; a chip sends its message; "Who hasn't paid us?"
  → prose in dialogue + table in drawer with row-count header; TRACE tab
  shows plan/versions/timings; pin behavior across a second question;
  "Delete all invoices" refusal renders as plain prose (no drawer); error
  card styling via a stopped-backend check; Esc dismisses drawer;
  reduced-motion spot check via emulation.
- Backend suite untouched — `pytest` stays green (no backend edits).
