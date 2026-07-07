import { MessageBubble } from "./MessageBubble";

export interface DisplayMessage {
  role: string;
  content: string;
}

export interface MessageListProps {
  messages: DisplayMessage[];
}

export function MessageList({ messages }: MessageListProps) {
  return (
    <div>
      {messages.map((message, index) => (
        <MessageBubble key={index} role={message.role} content={message.content} />
      ))}
    </div>
  );
}
