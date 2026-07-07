import { renderInlineMarkdown } from "./markdown";

export interface MessageBubbleProps {
  role: string;
  content: string;
}

export function MessageBubble({ role, content }: MessageBubbleProps) {
  return (
    <div data-role={role} style={{ margin: "0.5rem 0" }}>
      <strong>{role === "user" ? "You" : "Assistant"}:</strong>{" "}
      <span dangerouslySetInnerHTML={{ __html: renderInlineMarkdown(content) }} />
    </div>
  );
}
