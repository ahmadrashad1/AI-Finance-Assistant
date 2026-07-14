"use client";

import { useEffect } from "react";

import type { TableSegment } from "./markdown";
import { ResultTable } from "./ResultTable";
import { TracePanel } from "./TracePanel";
import styles from "./ResultDrawer.module.css";

export interface ResultArtifact {
  messageIndex: number;
  requestId?: string | undefined;
  title: string;
  tables: TableSegment[];
  rowCount: number;
}

export type DrawerTab = "result" | "trace";

export interface ResultDrawerProps {
  artifact: ResultArtifact;
  tab: DrawerTab;
  pinned: boolean;
  onTabChange: (tab: DrawerTab) => void;
  onTogglePin: () => void;
  onDismiss: () => void;
}

export function ResultDrawer({
  artifact,
  tab,
  pinned,
  onTabChange,
  onTogglePin,
  onDismiss,
}: ResultDrawerProps) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onDismiss();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onDismiss]);

  return (
    <aside className={styles.drawer} role="complementary" aria-label={artifact.title}>
      <div className={styles.bar} role="tablist">
        <button
          role="tab"
          aria-selected={tab === "result"}
          className={tab === "result" ? styles.tabActive : styles.tab}
          onClick={() => onTabChange("result")}
        >
          Result
        </button>
        {artifact.requestId && (
          <button
            role="tab"
            aria-selected={tab === "trace"}
            className={tab === "trace" ? styles.tabActive : styles.tab}
            onClick={() => onTabChange("trace")}
          >
            Trace
          </button>
        )}
        <span className={styles.spacer} />
        <button
          className={pinned ? styles.pinActive : styles.pin}
          aria-pressed={pinned}
          onClick={onTogglePin}
          title={pinned ? "Unpin" : "Pin this result"}
        >
          ⊙
        </button>
        <button className={styles.close} onClick={onDismiss} aria-label="Dismiss drawer">
          ✕
        </button>
      </div>
      <div className={styles.header}>
        {artifact.title} — {artifact.rowCount} {artifact.rowCount === 1 ? "row" : "rows"}
      </div>
      <div className={styles.body}>
        {tab === "result" &&
          artifact.tables.map((table, i) => <ResultTable key={i} table={table} />)}
        {tab === "trace" && artifact.requestId && <TracePanel requestId={artifact.requestId} />}
      </div>
    </aside>
  );
}
