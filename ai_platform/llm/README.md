# LLM Service

Provider-agnostic LLM access. The rest of the platform depends only on the
`LLMService` protocol — never on a concrete provider SDK — so swapping
providers is a configuration change, not a refactor.

- `LLMService` protocol: `complete()` (Phase-1 planning — returns the raw
  plan JSON) and `stream_reply()` (Phase-2 response generation — yields
  tokens).
- `GroqLLMService` and `AnthropicLLMService` implementations. Provider,
  model, and key come from configuration (`LLM_PROVIDER`, `LLM_MODEL`,
  `LLM_API_KEY` in `backend/.env`), never from code.

Nothing in this package may import orchestration, tools, domains, or the
backend app. It is constructed per request in `backend/app/api/chat.py`
(DI wiring) and handed to the `Planner` and `ChatWorkflow`; the evaluation
framework wraps it with recording/replay services
(`ai_platform/evaluation/cassette.py`).

Provider errors surface as the `AI` error category so users get a friendly
"assistant is busy" message while developers get the categorized log entry.
