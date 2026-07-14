"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

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

  const pinnedRef = useRef(false);
  const setPinned = useCallback((value: boolean) => {
    pinnedRef.current = value;
    setDrawerPinned(value);
  }, []);

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
    setPinned(false);
  }, [setPinned]);

  const handleShowArtifact = useCallback(
    (messageIndex: number) => {
      // An explicit click wins: open that artifact and clear any pin (spec).
      setDrawerIndex(messageIndex);
      setPinned(false);
      setDrawerTab("result");
    },
    [setPinned],
  );

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
      const assistantIndex = messages.length + 1;
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
            try {
              setConversations(await listConversations(sessionId));
            } catch {
              // Sidebar refresh is cosmetic here; never fail a delivered reply over it.
            }
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

        if (
          !pinnedRef.current &&
          splitMessageContent(assistantContent).some((s) => s.kind === "table")
        ) {
          setDrawerIndex(assistantIndex);
          setDrawerTab("result");
        }
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Something went wrong. Please try again.");
      } finally {
        setIsStreaming(false);
        setThinkingTool(null);
      }
    },
    [sessionId, activeConversationId, messages.length],
  );

  const handleTogglePin = useCallback(() => {
    const next = !pinnedRef.current;
    setPinned(next);
    if (!next && latestArtifact && latestArtifact.messageIndex !== drawerIndex) {
      setDrawerIndex(latestArtifact.messageIndex);
      setDrawerTab("result");
    }
  }, [latestArtifact, setPinned, drawerIndex]);

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
          onTogglePin={handleTogglePin}
          onDismiss={closeDrawer}
        />
      )}
    </main>
  );
}
