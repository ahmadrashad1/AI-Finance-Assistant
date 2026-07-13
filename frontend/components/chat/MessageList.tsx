import { MessageBubble } from "./MessageBubble";

export interface DisplayMessage {
  role: string;
  content: string;
  requestId?: string | undefined;
}

export interface MessageListProps {
  messages: DisplayMessage[];
}

export function MessageList({ messages }: MessageListProps) {
  return (
    <div>
      {messages.map((message, index) => (
        <MessageBubble
          key={index}
          role={message.role}
          content={message.content}
          requestId={message.requestId}
        />
      ))}
    </div>
  );
}
