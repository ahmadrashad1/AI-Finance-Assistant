"use client";

import { useEffect, useState } from "react";

import { getTrace, type RequestTrace } from "@/lib/api-client";

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
    return <p style={{ color: "red", fontSize: "0.85rem" }}>{error}</p>;
  }
  if (!trace) {
    return <p style={{ fontSize: "0.85rem" }}>Loading trace…</p>;
  }

  const firedBranch = Object.entries(trace.plan).find(
    ([, value]) => value !== null && value !== undefined && value !== false,
  );

  return (
    <div
      style={{
        border: "1px solid #ccc",
        borderRadius: "4px",
        padding: "0.5rem",
        margin: "0.25rem 0",
        fontSize: "0.85rem",
        background: "#fafafa",
      }}
    >
      <div>
        <strong>Plan:</strong> {firedBranch ? firedBranch[0] : "unknown"}
      </div>
      <div>
        <strong>Planning prompt:</strong> {trace.planning_prompt_version}{" "}
        <strong>System prompt:</strong> {trace.system_prompt_version}
      </div>
      <div>
        <strong>Total duration:</strong> {trace.total_duration_ms ?? "?"}ms
      </div>
      {trace.tool_executions.length > 0 && (
        <table style={{ marginTop: "0.5rem", borderCollapse: "collapse" }}>
          <thead>
            <tr>
              <th style={{ textAlign: "left", paddingRight: "0.5rem" }}>Tool</th>
              <th style={{ textAlign: "left", paddingRight: "0.5rem" }}>Status</th>
              <th style={{ textAlign: "left" }}>Duration</th>
            </tr>
          </thead>
          <tbody>
            {trace.tool_executions.map((execution, index) => (
              <tr key={index}>
                <td style={{ paddingRight: "0.5rem" }}>{execution.tool}</td>
                <td style={{ paddingRight: "0.5rem" }}>{execution.status}</td>
                <td>{execution.duration_ms}ms</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
