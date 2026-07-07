"use client";

import { useCallback, useEffect, useState } from "react";

import {
  getConversationMessages,
  getSessionId,
  listConversations,
  streamChat,
  type ConversationSummary,
} from "@/lib/api-client";
import { ConversationSidebar } from "@/components/chat/ConversationSidebar";
import { MessageInput } from "@/components/chat/MessageInput";
import { MessageList, type DisplayMessage } from "@/components/chat/MessageList";

export default function HomePage() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

  const handleSelectConversation = useCallback((conversationId: string) => {
    setActiveConversationId(conversationId);
    setError(null);
    getConversationMessages(conversationId)
      .then((history) =>
        setMessages(history.map((m) => ({ role: m.role, content: m.content }))),
      )
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Could not load messages.");
      });
  }, []);

  const handleNewConversation = useCallback(() => {
    setActiveConversationId(null);
    setMessages([]);
    setError(null);
  }, []);

  const handleSend = useCallback(
    async (message: string) => {
      if (!sessionId) {
        return;
      }
      setError(null);
      setMessages((prev) => [...prev, { role: "user", content: message }]);
      setIsStreaming(true);

      let assistantContent = "";
      setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

      try {
        for await (const event of streamChat(sessionId, message, activeConversationId)) {
          if (event.type === "tool_call") {
            setMessages((prev) => [
              ...prev.slice(0, -1),
              { role: "assistant", content: `Running ${event.tool}…` },
            ]);
          } else if (event.type === "token") {
            assistantContent += event.content;
            setMessages((prev) => [
              ...prev.slice(0, -1),
              { role: "assistant", content: assistantContent },
            ]);
          } else if (event.type === "done") {
            setActiveConversationId(event.conversation_id);
            const updated = await listConversations(sessionId);
            setConversations(updated);
          } else if (event.type === "error") {
            setError(event.message);
            setMessages((prev) => {
              const last = prev[prev.length - 1];
              if (last && last.role === "assistant" && (last.content === "" || last.content.startsWith("Running "))) {
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
      }
    },
    [sessionId, activeConversationId],
  );

  return (
    <main style={{ display: "flex", height: "100vh" }}>
      <ConversationSidebar
        conversations={conversations}
        activeConversationId={activeConversationId}
        onSelect={handleSelectConversation}
        onNewConversation={handleNewConversation}
        disabled={isStreaming}
      />
      <section style={{ flex: 1, display: "flex", flexDirection: "column", padding: "1rem" }}>
        <h1>AI Finance Assistant</h1>
        <div style={{ flex: 1, overflowY: "auto" }}>
          <MessageList messages={messages} />
        </div>
        {error && <p style={{ color: "red" }}>{error}</p>}
        <MessageInput disabled={isStreaming || !sessionId} onSend={handleSend} />
      </section>
    </main>
  );
}
