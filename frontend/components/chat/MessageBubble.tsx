"use client";

import { renderInlineMarkdown } from "./markdown";
import styles from "./MessageBubble.module.css";

export interface MessageBubbleProps {
  role: string;
  content: string;
  hasTables: boolean;
  onShowArtifact?: (() => void) | undefined;
}

export function MessageBubble({ role, content, hasTables, onShowArtifact }: MessageBubbleProps) {
  if (role === "user") {
    return (
      <div className={styles.userRow}>
        <span className={styles.userCard}>{content}</span>
      </div>
    );
  }

  return (
    <div className={styles.assistant}>
      <span
        className={styles.prose}
        dangerouslySetInnerHTML={{ __html: renderInlineMarkdown(content) }}
      />
      {hasTables && onShowArtifact && (
        <button type="button" className={styles.deskLink} onClick={onShowArtifact}>
          on the desk →
        </button>
      )}
    </div>
  );
}
