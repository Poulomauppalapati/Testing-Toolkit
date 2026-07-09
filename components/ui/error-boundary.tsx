"use client";

import { Component, type ReactNode } from "react";
import { AlertTriangle } from "lucide-react";

interface Props {
  children: ReactNode;
  /** Rendered when a descendant throws. Receives the error + a reset callback. */
  fallback?: (error: Error, reset: () => void) => ReactNode;
  /** Human label for the boundary, used in the default fallback + logging. */
  label?: string;
  /** Reset the boundary when this value changes (e.g. active dialog id). */
  resetKey?: unknown;
}

interface State {
  error: Error | null;
}

/**
 * Generic client error boundary. Prevents a fault in one subtree (e.g. a single
 * dialog) from white-screening the entire app. Recovering is as simple as
 * dismissing the fallback; the rest of the shell keeps running.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: { componentStack?: string | null }) {
    // Surface to the debug log without crashing.
    console.log(
      `[v0] ErrorBoundary(${this.props.label ?? "app"}) caught:`,
      error?.message,
      info?.componentStack ?? ""
    );
  }

  componentDidUpdate(prev: Props) {
    // Auto-reset when the guarded content changes (e.g. a different dialog
    // opens) so a previous crash doesn't stick around.
    if (prev.resetKey !== this.props.resetKey && this.state.error) {
      this.setState({ error: null });
    }
  }

  reset = () => this.setState({ error: null });

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;
    if (this.props.fallback) return this.props.fallback(error, this.reset);

    return (
      <div
        role="alert"
        className="flex flex-col items-center justify-center gap-3 rounded-lg border border-[var(--tt-danger,#e53e3e)]/40 bg-background p-6 text-center"
      >
        <AlertTriangle
          className="h-6 w-6 text-[var(--tt-danger,#e53e3e)]"
          aria-hidden="true"
        />
        <div>
          <p className="text-sm font-semibold text-[var(--tt-text-bright,inherit)]">
            Something went wrong{this.props.label ? ` in ${this.props.label}` : ""}
          </p>
          <p className="mt-1 text-xs text-[var(--tt-text-muted,#888)]">
            {error.message || "An unexpected error occurred."}
          </p>
        </div>
        <button
          type="button"
          onClick={this.reset}
          className="tt-btn tt-btn-ghost text-xs"
        >
          Try again
        </button>
      </div>
    );
  }
}
