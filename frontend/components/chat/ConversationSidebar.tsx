import type { ConversationSummary } from "@/lib/api-client";

import styles from "./ConversationSidebar.module.css";

export interface ConversationSidebarProps {
  conversations: ConversationSummary[];
  activeConversationId: string | null;
  onSelect: (conversationId: string) => void;
  onNewConversation: () => void;
  disabled: boolean;
}

export function ConversationSidebar({
  conversations,
  activeConversationId,
  onSelect,
  onNewConversation,
  disabled,
}: ConversationSidebarProps) {
  return (
    <aside className={styles.rail}>
      <div className={styles.brand}>
        <span className={styles.lamp} aria-hidden="true">✦</span> Atelier
      </div>
      <ul className={styles.list}>
        {conversations.map((conversation) => (
          <li key={conversation.id}>
            <button
              onClick={() => onSelect(conversation.id)}
              disabled={disabled}
              className={
                conversation.id === activeConversationId ? styles.itemActive : styles.item
              }
            >
              {conversation.title ?? "New conversation"}
            </button>
          </li>
        ))}
      </ul>
      <button onClick={onNewConversation} disabled={disabled} className={styles.newButton}>
        + New conversation
      </button>
    </aside>
  );
}
