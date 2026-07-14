# Frontend (Next.js)

A thin presentation layer: chat interface, markdown/table rendering, and
conversation UI state. It never contains business logic, never decides
which tools to call, and never talks directly to PostgreSQL — everything
goes through the FastAPI backend.

The home page is the chat: streamed assistant replies (SSE), markdown and
table rendering, a conversation sidebar, and a per-message "View trace"
panel showing the plan branch, prompt versions, timing, and tool executions
for that turn (correlated via the `x-request-id` response header). All
backend communication goes through `lib/api-client.ts`, a typed fetch
wrapper. TypeScript/ESLint tooling is configured in `tsconfig.json` and
`eslint.config.mjs`; `npm run lint`, `npm run typecheck`, and
`npm run build` are the CI checks.
