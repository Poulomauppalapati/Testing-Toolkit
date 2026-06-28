"use client";

import { useEffect, useRef, useState } from "react";
import { useAgent } from "@/lib/agent-context";
import { useAppState } from "@/lib/app-state";
import { useAppUpdate } from "@/lib/use-app-update";
import { getPreferences, setPendingReindexPref } from "@/lib/preferences";
import type { UpdateStatus } from "@/lib/agent-client";
import { AgentUpdateRequired } from "@/components/onboarding/AgentUpdateRequired";
import { ActivityBar } from "./ActivityBar";
import { NavPanel } from "./NavPanel";
import { StatusBar } from "./StatusBar";
import { BoardGrid } from "@/components/board/BoardGrid";
import { ActionBar } from "@/components/board/ActionBar";
import { LogPanel } from "@/components/board/LogPanel";
import { DialogHost } from "@/components/dialogs/DialogHost";

export function AppShell() {
  const { status } = useAgent();
  const {
    navVisible,
    logVisible,
    settings,
    reloadProjects,
    reindexAllKbs,
    pushLog,
  } = useAppState();
  const { check, apply } = useAppUpdate(pushLog);
  const bootstrapped = useRef(false);
  const reindexed = useRef(false);
  const autoUpdated = useRef(false);
  // When an agent update exists but can't be applied silently, we block the
  // whole app with AgentUpdateRequired until the user reinstalls.
  const [updateBlocked, setUpdateBlocked] = useState<UpdateStatus | null>(null);

  // Bootstrap: once connected & configured, load the project list (desktop
  // main.py _bootstrap -> reload_projects).
  useEffect(() => {
    if (
      status === "connected" &&
      settings?.configured &&
      !bootstrapped.current
    ) {
      bootstrapped.current = true;
      reloadProjects();
    }
  }, [status, settings?.configured, reloadProjects]);

  // On every refresh: once connected & configured, check for the latest agent
  // patch. Strategy is "silent first, then block":
  //   1. If an update exists and auto-update IS configured, apply it silently —
  //      apply() restarts the agent, waits for it, and reloads the page so the
  //      new code is live. The patch just "arrives" on refresh.
  //   2. If that silent apply can't happen (install not configured for
  //      auto-update) or it fails (unreachable/failed), the running agent is
  //      out of date with the shipped patch, so we BLOCK the whole app with
  //      AgentUpdateRequired and require a reinstall.
  // Nothing happens (no noise, no block) when already up to date.
  useEffect(() => {
    if (
      status === "connected" &&
      settings?.configured &&
      !autoUpdated.current
    ) {
      autoUpdated.current = true;
      void (async () => {
        const s = await check();
        if (!s?.update_available) return; // up to date or check failed
        if (s.configured) {
          pushLog?.(
            "INFO",
            `New patch available (v${s.latest}). Applying automatically...`
          );
          const applied = await apply(); // reloads the page on success
          if (applied) return;
        }
        // Either not configured for auto-update, or the silent apply failed.
        pushLog?.(
          "WARN",
          "Agent changes require a reinstall to take effect. Pausing the app."
        );
        setUpdateBlocked(s);
      })();
    }
  }, [status, settings?.configured, check, apply, pushLog]);

  // After a reinstall the agent restarts and the app reloads with a persisted
  // pendingReindex flag — rebuild every KB vector index once we're back online.
  useEffect(() => {
    if (
      status === "connected" &&
      settings?.configured &&
      !reindexed.current &&
      getPreferences().pendingReindex
    ) {
      reindexed.current = true;
      setPendingReindexPref(false);
      void reindexAllKbs();
    }
  }, [status, settings?.configured, reindexAllKbs]);

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="flex min-h-0 flex-1 overflow-hidden">
        {navVisible ? <NavPanel /> : <ActivityBar />}
        <main className="flex min-h-0 flex-1 flex-col gap-2 overflow-hidden px-2 py-2">
          <BoardGrid />
          <ActionBar />
          {logVisible && <LogPanel />}
        </main>
      </div>
      <StatusBar />
      <DialogHost />
      {updateBlocked && (
        <AgentUpdateRequired
          status={updateBlocked}
          onRetry={updateBlocked.configured ? apply : undefined}
        />
      )}
    </div>
  );
}
