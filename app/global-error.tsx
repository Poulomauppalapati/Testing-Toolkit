"use client";

import { useEffect } from "react";

/**
 * Global error boundary (Next.js App Router). Replaces the root layout when a
 * fault occurs in the layout itself, so it must be fully self-contained with
 * inline styles (globals.css is not guaranteed to be loaded here).
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.log("[v0] Global error boundary caught:", error?.message, error?.digest);
  }, [error]);

  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#0d1017",
          color: "#c7ccd6",
          fontFamily:
            "ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif",
        }}
      >
        <div style={{ maxWidth: 420, textAlign: "center", padding: 24 }}>
          <h1 style={{ fontSize: 16, fontWeight: 600, margin: "0 0 8px" }}>
            The app failed to load
          </h1>
          <p style={{ fontSize: 14, color: "#8a8fa3", margin: "0 0 16px" }}>
            A critical error occurred. Reloading usually resolves it.
          </p>
          <button
            type="button"
            onClick={reset}
            style={{
              cursor: "pointer",
              borderRadius: 6,
              border: "1px solid #3a6ea5",
              background: "#3a6ea5",
              color: "#fff",
              padding: "8px 16px",
              fontSize: 14,
            }}
          >
            Reload
          </button>
        </div>
      </body>
    </html>
  );
}
