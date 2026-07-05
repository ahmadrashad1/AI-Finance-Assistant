"use client";

import { useEffect, useState } from "react";

import { getHealth, type HealthResponse } from "@/lib/api-client";

type LoadState =
  | { kind: "loading" }
  | { kind: "loaded"; health: HealthResponse }
  | { kind: "error"; message: string };

export default function HomePage() {
  const [state, setState] = useState<LoadState>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;

    getHealth()
      .then((health) => {
        if (!cancelled) {
          setState({ kind: "loaded", health });
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setState({
            kind: "error",
            message: error instanceof Error ? error.message : "Unknown error",
          });
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main>
      <h1>AI Finance Assistant</h1>
      <p>
        The chat interface will live here. This placeholder confirms the connection to the
        FastAPI backend.
      </p>
      {state.kind === "loading" && <p>Checking backend status...</p>}
      {state.kind === "loaded" && (
        <p>
          Backend status: <strong>{state.health.status}</strong> (database:{" "}
          {state.health.database})
        </p>
      )}
      {state.kind === "error" && <p>Could not reach backend: {state.message}</p>}
    </main>
  );
}
