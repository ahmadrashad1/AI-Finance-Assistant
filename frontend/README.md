# Frontend (Next.js)

A thin presentation layer: chat interface, markdown/table rendering, and
conversation UI state. It never contains business logic, never decides
which tools to call, and never talks directly to PostgreSQL — everything
goes through the FastAPI backend.

No application code exists yet. TypeScript/ESLint tooling is configured in
`tsconfig.json` and `.eslintrc.json` in this directory.
