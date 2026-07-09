"use client";

import { useEffect } from "react";
import { AlertTriangle } from "lucide-react";

/**
 * Route-level error boundary (Next.js App Router convention). Catches any
 * uncaught render error in the page tree and offers recovery instead of a
 * blank white screen.
 */
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.log("[v0] Route error boundary caught:", error?.message, error?.digest);
  }, [error]);

  return (
    <div className="flex h-full min-h-screen items-center justify-center bg-background p-6">
      <div className="flex max-w-md flex-col items-center gap-4 text-center">
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[var(--tt-danger,#e53e3e)]/10">
          <AlertTriangle
            className="h-6 w-6 text-[var(--tt-danger,#e53e3e)]"
            aria-hidden="true"
          />
        </div>
        <div>
          <h1 className="text-base font-semibold text-[var(--tt-text-bright,inherit)]">
            The app hit an unexpected error
          </h1>
          <p className="mt-1 text-sm text-[var(--tt-text-muted,#888)]">
            Your work in the agent is safe. Try again to recover the session.
          </p>
          {error?.message && (
            <p className="mt-2 break-words text-xs text-[var(--tt-text-faint,#aaa)]">
              {error.message}
            </p>
          )}
        </div>
        <button type="button" onClick={reset} className="tt-btn tt-btn-primary">
          Try again
        </button>
      </div>
    </div>
  );
}
