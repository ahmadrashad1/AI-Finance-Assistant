"use client";

import { useState } from "react";

export interface MessageInputProps {
  disabled: boolean;
  onSend: (message: string) => void;
}

export function MessageInput({ disabled, onSend }: MessageInputProps) {
  const [value, setValue] = useState("");

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    const trimmed = value.trim();
    if (!trimmed || disabled) {
      return;
    }
    onSend(trimmed);
    setValue("");
  };

  return (
    <form onSubmit={handleSubmit}>
      <input
        type="text"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder="Ask about your finances..."
        disabled={disabled}
        style={{ width: "80%" }}
      />
      <button type="submit" disabled={disabled}>
        Send
      </button>
    </form>
  );
}
