# Conversation Memory

Stores and retrieves conversation state (messages, prior tool calls, prior
results) for the orchestration engine. Retrieval is selective: the LLM
receives only the relevant slice of context needed to resolve references
like "those" or "the ones above $5,000," never the entire conversation
history.
