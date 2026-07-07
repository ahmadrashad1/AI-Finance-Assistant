import type { ConversationSummary } from "@/lib/api-client";

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
    <aside style={{ width: "220px", borderRight: "1px solid #ccc", padding: "0.5rem" }}>
      <button
        onClick={onNewConversation}
        disabled={disabled}
        style={{ width: "100%", marginBottom: "0.5rem" }}
      >
        + New conversation
      </button>
      <ul style={{ listStyle: "none", padding: 0 }}>
        {conversations.map((conversation) => (
          <li key={conversation.id}>
            <button
              onClick={() => onSelect(conversation.id)}
              disabled={disabled}
              style={{
                width: "100%",
                textAlign: "left",
                fontWeight: conversation.id === activeConversationId ? "bold" : "normal",
              }}
            >
              {conversation.title ?? "New conversation"}
            </button>
          </li>
        ))}
      </ul>
    </aside>
  );
}
