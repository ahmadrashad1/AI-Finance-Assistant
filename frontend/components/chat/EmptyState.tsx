"use client";

import { useEffect, useState } from "react";

import styles from "./EmptyState.module.css";

export interface EmptyStateProps {
  onPick: (question: string) => void;
  disabled: boolean;
}

const SUGGESTIONS = [
  "Who hasn't paid us?",
  "Generate an aging report",
  "Find duplicate invoices",
];

function greeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) {
    return "Good morning. The books are open.";
  }
  if (hour < 18) {
    return "Good afternoon. The books are open.";
  }
  return "Good evening. The books are open.";
}

export function EmptyState({ onPick, disabled }: EmptyStateProps) {
  const [greetingText, setGreetingText] = useState("The books are open.");
  useEffect(() => {
    setGreetingText(greeting());
  }, []);

  return (
    <div className={styles.room}>
      <div className={styles.kicker}>Northwind Manufacturing · Finance</div>
      <h1 className={styles.greeting}>{greetingText}</h1>
      <div className={styles.chips}>
        {SUGGESTIONS.map((question) => (
          <button
            key={question}
            className={styles.chip}
            onClick={() => onPick(question)}
            disabled={disabled}
          >
            {question}
          </button>
        ))}
      </div>
    </div>
  );
}
