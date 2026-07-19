"use client";

import { useEffect, useRef, useState } from "react";
import { useAgent } from "@/lib/agent-context";
import { agent, type SettingsResponse } from "@/lib/agent-client";
import { AppStateProvider } from "@/lib/app-state";
import { OnboardingScreen } from "@/components/onboarding/OnboardingScreen";
import { AppShell } from "@/components/layout/AppShell";
import { getPreferences, setPendingReinstallPref } from "@/lib/preferences";
import { isAgentOutdated } from "@/lib/agent-version";
import { getReinstallReason, clearReinstallReason } from "@/lib/reinstall";
import type { ReinstallReason } from "@/lib/reinstall";

export default function Home() {
  const { status, health } = useAgent();
  const [reinstalling, setReinstalling] = useState(false);
  const [reason, setReason] = useState<ReinstallReason>("reinstall");
  useEffect(() => {
    const prefs = getPreferences();
    setReinstalling(prefs.pendingReinstall);
    if (prefs.pendingReinstall) setReason(getReinstallReason());
  }, []);

  // Auto-dismiss: if the agent reconnects at an acceptable version while the
  // installer screen is showing, let OnboardingScreen handle the dismiss via
  // its own sawDrop + version-aware fallback (both gated on downloaded=true).
  // The page-level effect only handles the edge case where the screen was
  // entered for a plain "reinstall" and the agent never went offline — the
  // original-version check prevents an immediate dismiss on entry.
  const agentVersion = health?.version ?? null;
  const entryVersion = useRef<string | null>(null);
  useEffect(() => {
    if (reinstalling && agentVersion && !entryVersion.current) {
      entryVersion.current = agentVersion;
    }
  }, [reinstalling, agentVersion]);
  useEffect(() => {
    if (!reinstalling || status !== "connected" || !agentVersion) return;
    // Never dismiss if the agent version hasn't changed since entry — the
    // user hasn't run the installer yet.
    if (agentVersion === entryVersion.current) return;
    if (!isAgentOutdated(agentVersion)) {
      setPendingReinstallPref(false);
      clearReinstallReason();
      setReinstalling(false);
    }
  }, [reinstalling, status, agentVersion, reason]);

  if (reinstalling) {
    return (
      <OnboardingScreen
        reinstall
        reason={reason}
        onReinstallComplete={() => {
          setPendingReinstallPref(false);
          clearReinstallReason();
          setReinstalling(false);
        }}
        onReinstallCancel={() => {
          setPendingReinstallPref(false);
          clearReinstallReason();
          setReinstalling(false);
        }}
      />
    );
  }

  if (status === "connecting") return <LoadingScreen label="Connecting to agent..." />;
  if (status === "offline") return <OnboardingScreen />;
  return <ConnectedApp />;
}

function ConnectedApp() {
  const [settings, setSettings] = useState<SettingsResponse | null | undefined>(
    undefined
  );

  useEffect(() => {
    agent
      .getSettings()
      .then(setSettings)
      .catch(() => setSettings(null));
  }, []);

  if (settings === undefined) return <LoadingScreen label="Loading settings..." />;

  return (
    <AppStateProvider initialSettings={settings}>
      <AppShell />
    </AppStateProvider>
  );
}

function LoadingScreen({ label }: { label: string }) {
  return (
    <div className="flex h-full items-center justify-center bg-background">
      <div className="flex flex-col items-center gap-4">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-[var(--tt-outline)] border-t-[var(--tt-primary)]" />
        <p className="text-sm text-muted-foreground">{label}</p>
      </div>
    </div>
  );
}
