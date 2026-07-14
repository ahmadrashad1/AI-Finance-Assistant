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
