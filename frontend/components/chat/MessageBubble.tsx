"use client";

import { useState } from "react";

import { renderInlineMarkdown } from "./markdown";
import { TracePanel } from "./TracePanel";

export interface MessageBubbleProps {
  role: string;
  content: string;
  requestId?: string | undefined;
}

export function MessageBubble({ role, content, requestId }: MessageBubbleProps) {
  const [showTrace, setShowTrace] = useState(false);

  return (
    <div data-role={role} style={{ margin: "0.5rem 0" }}>
      <strong>{role === "user" ? "You" : "Assistant"}:</strong>{" "}
      <span dangerouslySetInnerHTML={{ __html: renderInlineMarkdown(content) }} />
      {role === "assistant" && requestId && (
        <>
          {" "}
          <button
            type="button"
            onClick={() => setShowTrace((prev) => !prev)}
            style={{ fontSize: "0.75rem", cursor: "pointer" }}
          >
            {showTrace ? "Hide trace" : "View trace"}
          </button>
          {showTrace && <TracePanel requestId={requestId} />}
        </>
      )}
    </div>
  );
}
