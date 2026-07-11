"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useAgent } from "@/lib/agent-context";
import { useAppState } from "@/lib/app-state";
import {
  AGENT_UPDATE_REQUIRED_EVENT,
  useAppUpdate,
} from "@/lib/use-app-update";
import { useWebFreshness } from "@/lib/use-web-freshness";
import { isAgentOutdated, REQUIRED_AGENT_VERSION } from "@/lib/agent-version";
import {
  isFirstLaunchToday,
  markUpdateCheckedToday,
} from "@/lib/preferences";
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
  const { status, health } = useAgent();
  const { navVisible, logVisible, settings, reloadProjects, pushLog } =
    useAppState();
  const { check } = useAppUpdate(pushLog);
  const bootstrapped = useRef(false);
  const updateChecked = useRef(false);
  // Agent updates are detection-only. When one is found, block the app with
  // AgentUpdateRequired until the user refreshes the agent via the installer.
  const [updateBlocked, setUpdateBlocked] = useState<UpdateStatus | null>(null);

  // (B) Keep the WEB app itself current: reload the tab when a newer deployment
  // ships. The orchestrator must be fresh for the other guarantees to hold.
  useWebFreshness();

  // The agent version reported by /health, used for the (A) handshake below.
  const agentVersion = health?.version ?? null;

  // Bootstrap: once connected & configured, load the project list.
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

  // (A) Minimum-version handshake — the hard guarantee. The web app knows the
  // lowest agent version it works with (REQUIRED_AGENT_VERSION). The moment a
  // connected agent reports an older version, BLOCK the whole app immediately
  // and unconditionally — no GitHub, manifest, or update-config dependency. A
  // newer-than-required agent is fine. This runs on every connect/version change
  // and cannot be bypassed by network failures, so a stale agent is never
  // silently usable against this build.
  useEffect(() => {
    if (status !== "connected" || !agentVersion) return;
    if (isAgentOutdated(agentVersion)) {
      setUpdateBlocked((prev) =>
        prev?.current === agentVersion
          ? prev
          : {
              current: agentVersion,
              latest: REQUIRED_AGENT_VERSION,
              update_available: true,
              // We don't yet know if auto-update is configured; the check below
              // refines this. Default false so the gate shows reinstall first.
              configured: false,
              reachable: true,
              install_dir: "",
            }
      );
    }
  }, [status, agentVersion]);

  // Detection only: a newer manifest version pauses the app and offers a
  // reinstall. No update configuration, patch download, apply, or restart API
  // is called from the web app.
  const runUpdateCheck = useCallback(async () => {
    const next = await check();
    if (next?.update_available) setUpdateBlocked(next);
  }, [check]);

  // Manual checks in the nav, rail, or Settings use separate hook instances.
  // Their detection result is announced through this browser-only event so the
  // single shell-owned blocking gate opens consistently from every entry point.
  useEffect(() => {
    const onRequired = (event: Event) => {
      setUpdateBlocked((event as CustomEvent<UpdateStatus>).detail);
    };
    window.addEventListener(AGENT_UPDATE_REQUIRED_EVENT, onRequired);
    return () =>
      window.removeEventListener(AGENT_UPDATE_REQUIRED_EVENT, onRequired);
  }, []);

  // Configured sessions run a detection-only manifest check on every refresh.
  // The first connected launch of each day checks even before source setup so
  // shipped agent changes are surfaced without mutating a live installation.
  useEffect(() => {
    if (status !== "connected" || updateChecked.current) return;
    if (!settings?.configured && !isFirstLaunchToday()) return;
    updateChecked.current = true;
    markUpdateCheckedToday();
    void runUpdateCheck();
  }, [status, settings?.configured, runUpdateCheck]);

  // (C) Harden detection for long-open sessions: re-check on tab focus, when the
  // network returns, and on a periodic interval — not just at launch. These are
  // no-ops while offline or already up to date.
  useEffect(() => {
    if (status !== "connected") return;
    const recheck = () => {
      if (settings?.configured || isFirstLaunchToday()) {
        markUpdateCheckedToday();
        void runUpdateCheck();
      }
    };
    const onFocus = () => recheck();
    const onOnline = () => recheck();
    const interval = setInterval(recheck, 30 * 60 * 1000); // every 30 min
    window.addEventListener("focus", onFocus);
    window.addEventListener("online", onOnline);
    return () => {
      clearInterval(interval);
      window.removeEventListener("focus", onFocus);
      window.removeEventListener("online", onOnline);
    };
  }, [status, settings?.configured, runUpdateCheck]);

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="flex min-h-0 flex-1 overflow-hidden">
        {navVisible ? <NavPanel /> : <ActivityBar />}
        <main className="flex min-h-0 flex-1 flex-col overflow-hidden">
          {/* Board grid fills the space; the action bar sits BELOW it (desktop
              parity — main_window stacks the grid, then the action row, then
              the log dock at the bottom). */}
          <div className="flex min-h-0 flex-1 flex-col overflow-hidden px-2 py-2">
            <BoardGrid />
          </div>
          <ActionBar />
          {logVisible && <LogPanel />}
        </main>
      </div>
      <StatusBar />
      <DialogHost />
      {updateBlocked && <AgentUpdateRequired status={updateBlocked} />}
    </div>
  );
}
