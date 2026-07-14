# Frontend (Next.js)

A thin presentation layer: chat interface, markdown/table rendering, and
conversation UI state. It never contains business logic, never decides
which tools to call, and never talks directly to PostgreSQL — everything
goes through the FastAPI backend.

The home page is "The Atelier": a dark, lamp-lit workspace. Assistant prose
renders in a serif voice directly on the wall; any reply containing tables
sends them to a right-side result drawer (RESULT/TRACE tabs, pin, Esc to
dismiss) so data gets room while the dialogue stays readable. While tools
run, a brass lamp pulses ("Consulting the ledgers — …", business phrases
from `components/chat/toolNames.ts`, never raw tool names). The TRACE tab
shows the plan branch, prompt versions, timing, and tool executions for
that turn (correlated via the `x-request-id` response header). Design
tokens live in `app/globals.css`; each component has a co-located CSS
Module; fonts (Fraunces + JetBrains Mono) load via `next/font`. All
backend communication goes through `lib/api-client.ts`, a typed fetch
wrapper. TypeScript/ESLint tooling is configured in `tsconfig.json` and
`eslint.config.mjs`; `npm run lint`, `npm run typecheck`, and
`npm run build` are the CI checks.
