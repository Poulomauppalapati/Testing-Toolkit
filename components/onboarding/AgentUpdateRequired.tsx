"use client";

import { AlertTriangle, Download } from "lucide-react";
import type { UpdateStatus } from "@/lib/agent-client";
import { requestReinstall } from "@/lib/reinstall";

/** Non-dismissable compatibility gate with one supported upgrade action. */
export function AgentUpdateRequired({ status }: { status: UpdateStatus }) {
  return (
    <div
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="agent-update-title"
      className="fixed inset-0 z-[100] flex items-center justify-center bg-background/95 px-6 backdrop-blur-sm"
    >
      <div className="tt-dialog w-full max-w-lg p-7">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-amber-500/15">
            <AlertTriangle className="h-5 w-5 text-amber-400" strokeWidth={2} />
          </div>
          <div>
            <h1
              id="agent-update-title"
              className="text-balance text-lg font-bold tracking-tight text-foreground"
            >
              Agent update required
            </h1>
            <p className="mt-1 text-pretty text-sm leading-relaxed text-muted-foreground">
              A newer Testing Toolkit agent is available. Update the agent to
              continue with the compatible version of the app.
            </p>
          </div>
        </div>

        <div className="tt-input mt-5 flex flex-col gap-2 !p-3 text-xs">
          <div className="flex items-center justify-between gap-3">
            <span className="text-muted-foreground">Installed version</span>
            <span className="font-mono text-foreground">
              {status.current ?? "unknown"}
            </span>
          </div>
          <div className="flex items-center justify-between gap-3">
            <span className="text-muted-foreground">Required version</span>
            <span className="font-mono text-foreground">
              {status.latest ?? "latest"}
            </span>
          </div>
        </div>

        <div className="mt-6 flex justify-end">
          <button
            className="tt-btn-primary flex items-center justify-center gap-2"
            onClick={() => requestReinstall("update")}
          >
            <Download className="h-4 w-4" strokeWidth={2} />
            Update application
          </button>
        </div>

        <p className="mt-4 text-[11px] leading-relaxed text-muted-foreground">
          Your settings, credentials, preferences, selected project and board,
          generated artifacts, and completed onboarding are preserved. After
          reconnecting, only stale or incompatible knowledge-base indexes are
          rebuilt.
        </p>
      </div>
    </div>
  );
}
