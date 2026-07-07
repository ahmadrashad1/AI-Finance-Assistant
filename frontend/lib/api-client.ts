export interface HealthResponse {
  status: "healthy" | "degraded";
  app: string;
  database: string;
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export async function getHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/api/health`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Health check failed with status ${response.status}`);
  }
  return (await response.json()) as HealthResponse;
}

export interface ChatTokenEvent {
  type: "token";
  content: string;
}

export interface ChatDoneEvent {
  type: "done";
  conversation_id: string;
}

export interface ChatErrorEvent {
  type: "error";
  message: string;
}

export type ChatStreamEvent = ChatTokenEvent | ChatDoneEvent | ChatErrorEvent;

export interface ConversationSummary {
  id: string;
  title: string | null;
  created_at: string;
}

export interface ConversationMessage {
  role: string;
  content: string;
  created_at: string;
}

const SESSION_ID_STORAGE_KEY = "ai-finance-assistant-session-id";

export function getSessionId(): string {
  const existing = window.localStorage.getItem(SESSION_ID_STORAGE_KEY);
  if (existing) {
    return existing;
  }
  const generated = crypto.randomUUID();
  window.localStorage.setItem(SESSION_ID_STORAGE_KEY, generated);
  return generated;
}

export async function* streamChat(
  sessionId: string,
  message: string,
  conversationId: string | null,
): AsyncGenerator<ChatStreamEvent> {
  const response = await fetch(`${API_BASE_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      message,
      conversation_id: conversationId,
    }),
  });
  if (!response.ok || !response.body) {
    throw new Error(`Chat request failed with status ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() ?? "";
    for (const chunk of chunks) {
      const trimmed = chunk.trim();
      if (trimmed.startsWith("data:")) {
        yield JSON.parse(trimmed.slice("data:".length).trim()) as ChatStreamEvent;
      }
    }
  }
}

export async function listConversations(sessionId: string): Promise<ConversationSummary[]> {
  const response = await fetch(
    `${API_BASE_URL}/api/chat/conversations?session_id=${encodeURIComponent(sessionId)}`,
    { cache: "no-store" },
  );
  if (!response.ok) {
    throw new Error(`Failed to list conversations with status ${response.status}`);
  }
  return (await response.json()) as ConversationSummary[];
}

export async function getConversationMessages(
  conversationId: string,
): Promise<ConversationMessage[]> {
  const response = await fetch(
    `${API_BASE_URL}/api/chat/conversations/${conversationId}/messages`,
    { cache: "no-store" },
  );
  if (!response.ok) {
    throw new Error(`Failed to load messages with status ${response.status}`);
  }
  return (await response.json()) as ConversationMessage[];
}
