"use client";

import { useState } from "react";

import styles from "./MessageInput.module.css";

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
    <form onSubmit={handleSubmit} className={styles.form}>
      <input
        type="text"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder="Ask the books anything…"
        disabled={disabled}
        className={styles.input}
      />
      <button type="submit" disabled={disabled} className={styles.send} aria-label="Send">
        ↵
      </button>
    </form>
  );
}
