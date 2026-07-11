"use client";

import { useCallback, useState } from "react";
import { agent, type UpdateStatus } from "./agent-client";

type Pushed = (
  level: "INFO" | "SUCCESS" | "WARN" | "ERROR",
  text: string
) => void;

export const AGENT_UPDATE_REQUIRED_EVENT = "tt:agent-update-required";

/** Notify the shell that version detection found a newer agent. */
export function announceAgentUpdateRequired(status: UpdateStatus) {
  if (typeof window === "undefined") return;
  window.dispatchEvent(
    new CustomEvent<UpdateStatus>(AGENT_UPDATE_REQUIRED_EVENT, {
      detail: status,
    })
  );
}

/**
 * Detection-only agent update policy.
 *
 * This hook never configures, downloads, applies, polls, or restarts the local
 * agent. A newer version is announced to AppShell, which pauses the app and
 * presents the single supported upgrade path: reinstalling the agent while
 * preserving user data and completed onboarding.
 */
export function useAppUpdate(pushLog?: Pushed) {
  const [checking, setChecking] = useState(false);
  const [status, setStatus] = useState<UpdateStatus | null>(null);

  const log: Pushed = useCallback(
    (level, text) => pushLog?.(level, text),
    [pushLog]
  );

  const check = useCallback(async (): Promise<UpdateStatus | null> => {
    setChecking(true);
    try {
      const next = await agent.updateStatus();
      setStatus(next);
      if (next.update_available) {
        log(
          "WARN",
          `Agent v${next.latest ?? "latest"} is available. Reinstall is required.`
        );
        announceAgentUpdateRequired(next);
      } else if (next.reachable) {
        log("SUCCESS", `Agent v${next.current} is up to date.`);
      } else {
        log("WARN", "Could not reach the update server. No changes were made.");
      }
      return next;
    } catch (error) {
      log(
        "WARN",
        `Could not check for agent updates: ${(error as Error).message}`
      );
      return null;
    } finally {
      setChecking(false);
    }
  }, [log]);

  return {
    phase: checking ? ("checking" as const) : ("idle" as const),
    status,
    check,
    busy: checking,
  };
}
