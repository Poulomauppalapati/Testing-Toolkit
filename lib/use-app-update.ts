"use client";

/**
 * use-app-update.ts
 * Shared "refresh the app for new patches" flow used by both the sidebar
 * top button and the Settings > Installation section.
 *
 * The local Python agent self-updates from a GitHub manifest. Triggering it
 * on demand downloads the latest source, applies it, and restarts the agent.
 * After a successful apply we poll /health until the freshly-restarted agent
 * answers again, then reload the page so the browser picks up any frontend
 * changes too.
 */

import { useCallback, useState } from "react";
import {
  agent,
  type UpdateStatus,
  type UpdateProgress,
} from "./agent-client";
import { compareVersions } from "./agent-version";

type Pushed = (level: "INFO" | "SUCCESS" | "WARN" | "ERROR", text: string) => void;

export type UpdatePhase =
  | "idle"
  | "checking"
  | "applying"
  | "restarting"
  | "done";

/** Friendly fallback labels per phase, used when the agent doesn't send one. */
const PHASE_LABELS: Record<string, string> = {
  starting: "Preparing update…",
  downloading: "Downloading update…",
  installing_deps: "Installing dependencies…",
  staging: "Applying files…",
  restarting: "Restarting the agent…",
  reconnecting: "Reconnecting…",
  done: "Update complete",
  failed: "Update failed",
};

/** Live, UI-facing snapshot of an in-progress update for the overlay screen. */
export interface AppUpdateProgress {
  /** Coarse phase that drives the message/animation. */
  phase: string;
  /** Human-readable status line shown under the title. */
  message: string;
  /** 0–100 overall percentage for the bar. */
  percent: number;
  /** Target version being installed, when known. */
  version?: string | null;
  /** True while we can't read a precise percent (indeterminate bar). */
  indeterminate: boolean;
}

export function useAppUpdate(pushLog?: Pushed) {
  const [phase, setPhase] = useState<UpdatePhase>("idle");
  const [status, setStatus] = useState<UpdateStatus | null>(null);
  const [progress, setProgress] = useState<AppUpdateProgress | null>(null);

  const log: Pushed = useCallback(
    (level, text) => pushLog?.(level, text),
    [pushLog]
  );

  /** Non-destructive version check. Returns the status (also stored). */
  const check = useCallback(async (): Promise<UpdateStatus | null> => {
    setPhase("checking");
    try {
      const s = await agent.updateStatus();
      setStatus(s);
      return s;
    } catch (e) {
      log("WARN", `Could not check for updates: ${(e as Error).message}`);
      return null;
    } finally {
      setPhase((p) => (p === "checking" ? "idle" : p));
    }
  }, [log]);

  /**
   * Make auto-update self-sufficient: if the agent isn't configured for updates
   * (token-less / older install), fetch the read-only update token from the
   * SSO-protected web app and hand it to the agent's /update/config. This is the
   * key to fully autonomous updates — afterwards the agent's own 60s poller and
   * the on-refresh check both work, with no reinstall and no human step.
   * Returns the (possibly refreshed) status. Always best-effort.
   */
  const ensureConfigured = useCallback(
    async (current?: UpdateStatus | null): Promise<UpdateStatus | null> => {
      const s = current ?? (await check());
      if (!s || s.configured) return s; // already self-updating, or can't tell
      try {
        const res = await fetch("/api/agent-update/config", {
          cache: "no-store",
        });
        if (!res.ok) return s; // web app has no token configured server-side
        const cfg = await res.json();
        if (!cfg?.token) return s;
        const healed = await agent.configureUpdate({
          token: cfg.token,
          repo: cfg.repo,
          ref: cfg.ref,
          manifest_url: cfg.manifest_url,
        });
        if (healed) {
          setStatus(healed);
          log("INFO", "Auto-update enabled for this install.");
          return healed;
        }
      } catch {
        // Network / agent hiccup — leave as-is; we retry on the next check.
      }
      return s;
    },
    [check, log]
  );

  /** Map an agent UpdateProgress snapshot into our UI-facing progress shape. */
  const pushProgress = useCallback((p: UpdateProgress) => {
    setProgress({
      phase: p.phase,
      message: p.message || PHASE_LABELS[p.phase] || "Updating…",
      percent: Math.max(0, Math.min(100, Math.round(p.percent || 0))),
      version: p.version || null,
      indeterminate: !p.percent,
    });
  }, []);

  /**
   * Poll GET /update/progress until the apply reaches a terminal/restart state.
   * Returns the last phase seen ("restarting" on success, "failed", etc.) or
   * null if the agent has no progress route (older build → indeterminate UI).
   */
  const pollProgress = useCallback(
    async (version: string | null): Promise<string | null> => {
      const start = Date.now();
      let sawRoute = false;
      while (Date.now() - start < 120000) {
        let snap: UpdateProgress | null = null;
        try {
          snap = await agent.updateProgress();
        } catch {
          // Agent stopped answering — almost certainly the restart began.
          return "restarting";
        }
        if (snap === null) {
          // Route missing (older agent). Show an indeterminate bar and stop.
          if (!sawRoute) {
            setProgress({
              phase: "applying",
              message: "Updating the agent…",
              percent: 0,
              version,
              indeterminate: true,
            });
          }
          return null;
        }
        sawRoute = true;
        pushProgress(snap);
        if (
          snap.phase === "restarting" ||
          snap.phase === "failed" ||
          snap.phase === "done" ||
          snap.phase === "up_to_date"
        ) {
          return snap.phase;
        }
        await new Promise((r) => setTimeout(r, 700));
      }
      return "restarting"; // timed out waiting — assume it moved on to restart
    },
    [pushProgress]
  );

  /** Wait until the agent answers /health again after a restart. */
  const waitForReconnect = useCallback(
    async (timeoutMs = 60000) => {
      const start = Date.now();
      // Give the old process a moment to exit before we start polling.
      await new Promise((r) => setTimeout(r, 1500));
      while (Date.now() - start < timeoutMs) {
        const ok = await agent.checkConnection();
        if (ok === "connected") return true;
        // Creep the bar from ~96% toward 99% while we wait for the relaunch so
        // it never looks stuck during the headless restart.
        setProgress((prev) =>
          prev
            ? {
                ...prev,
                phase: "reconnecting",
                message: PHASE_LABELS.reconnecting,
                percent: Math.min(99, Math.max(prev.percent, 96) + 1),
                indeterminate: false,
              }
            : prev
        );
        await new Promise((r) => setTimeout(r, 1500));
      }
      return false;
    },
    []
  );

  /**
   * Apply the latest patch. Returns true if an update was applied (and the app
   * is about to reload), false otherwise (already current / not configured).
   */
  const apply = useCallback(async (): Promise<boolean> => {
    setPhase("applying");
    log("INFO", "Checking for the latest patch...");
    try {
      const r = await agent.applyUpdate();
      if (r.status === "not_configured") {
        log("WARN", "Automatic updates are not configured for this install.");
        setPhase("idle");
        setProgress(null);
        return false;
      }
      if (r.status === "unreachable") {
        log("WARN", "Could not reach the update server. Check your connection.");
        setPhase("idle");
        setProgress(null);
        return false;
      }
      if (r.status === "failed") {
        log("ERROR", "Update failed to apply. The agent kept the current version.");
        setPhase("idle");
        setProgress(null);
        return false;
      }
      if (r.status === "up_to_date" || (!r.applied && r.status !== "started")) {
        log("SUCCESS", `You're already on the latest version (v${r.current}).`);
        setPhase("idle");
        setProgress(null);
        return false;
      }

      // An update is now downloading/applying.
      log("INFO", `Updating to v${r.latest ?? "latest"}…`);
      setProgress({
        phase: "starting",
        message: PHASE_LABELS.starting,
        percent: 2,
        version: r.latest,
        indeterminate: false,
      });

      // Newer agents (>=1.10.0) return "started" and apply in the background, so
      // we poll for live progress. Older agents return "applied" synchronously
      // (already restarting) — skip straight to the reconnect wait.
      if (r.status === "started") {
        const last = await pollProgress(r.latest);
        if (last === "failed") {
          log("ERROR", "Update failed to apply. The agent kept the current version.");
          setPhase("idle");
          setProgress(null);
          return false;
        }
        if (last === "up_to_date") {
          log("SUCCESS", `You're already on the latest version (v${r.current}).`);
          setPhase("idle");
          setProgress(null);
          return false;
        }
      }

      // The agent is restarting (headless). Wait for it to answer again.
      log("INFO", "Restarting the agent...");
      setPhase("restarting");
      setProgress((prev) => ({
        phase: "restarting",
        message: PHASE_LABELS.restarting,
        percent: prev ? Math.max(prev.percent, 96) : 96,
        version: prev?.version ?? r.latest,
        indeterminate: false,
      }));
      const back = await waitForReconnect();
      setPhase("done");
      if (!back) {
        log(
          "WARN",
          "Update applied, but the agent is taking a while to restart. " +
            "Reload the page in a moment."
        );
        return true;
      }

      // Post-apply verification: confirm the restarted agent actually reports
      // the expected version. If it didn't advance, the apply silently didn't
      // take effect — treat that as a failure so the caller can fall through to
      // the block-and-reinstall path instead of believing we're up to date.
      if (r.latest) {
        try {
          const h = await agent.health();
          if (compareVersions(h.version, r.latest) < 0) {
            log(
              "ERROR",
              `Update did not take effect (agent still v${h.version}, expected v${r.latest}).`
            );
            setPhase("idle");
            return false;
          }
        } catch {
          // Couldn't read health to verify — fall through and reload anyway;
          // the next launch's handshake will re-evaluate.
        }
      }

      setProgress({
        phase: "done",
        message: PHASE_LABELS.done,
        percent: 100,
        version: r.latest,
        indeterminate: false,
      });
      log("SUCCESS", "Update applied. Reloading the app...");
      await new Promise((r) => setTimeout(r, 600));
      if (typeof window !== "undefined") window.location.reload();
      return true;
    } catch (e) {
      log("ERROR", `Update failed: ${(e as Error).message}`);
      setPhase("idle");
      setProgress(null);
      return false;
    }
  }, [log, waitForReconnect, pollProgress]);

  return {
    phase,
    status,
    progress,
    check,
    apply,
    ensureConfigured,
    busy: phase !== "idle" && phase !== "done",
  };
}
