"use client";

import { useEffect, useState } from "react";

import { getTrace, type RequestTrace } from "@/lib/api-client";
import styles from "./TracePanel.module.css";

export interface TracePanelProps {
  requestId: string;
}

export function TracePanel({ requestId }: TracePanelProps) {
  const [trace, setTrace] = useState<RequestTrace | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getTrace(requestId)
      .then(setTrace)
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Could not load trace.");
      });
  }, [requestId]);

  if (error) {
    return <p className={styles.error}>{error}</p>;
  }
  if (!trace) {
    return <p className={styles.loading}>Loading trace…</p>;
  }

  const firedBranch = Object.entries(trace.plan).find(
    ([, value]) => value !== null && value !== undefined && value !== false,
  );

  return (
    <div className={styles.panel}>
      <div className={styles.line}>
        <strong>Plan:</strong> {firedBranch ? firedBranch[0] : "unknown"}
      </div>
      <div className={styles.line}>
        <strong>Planning prompt:</strong> {trace.planning_prompt_version}{" "}
        <strong>System prompt:</strong> {trace.system_prompt_version}
      </div>
      <div className={styles.line}>
        <strong>Total duration:</strong> {trace.total_duration_ms ?? "?"}ms
      </div>
      {trace.tool_executions.length > 0 && (
        <table className={styles.traceTable}>
          <thead>
            <tr>
              <th>Tool</th>
              <th>Status</th>
              <th>Duration</th>
            </tr>
          </thead>
          <tbody>
            {trace.tool_executions.map((execution, index) => (
              <tr key={index}>
                <td>{execution.tool}</td>
                <td>{execution.status}</td>
                <td>{execution.duration_ms}ms</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
