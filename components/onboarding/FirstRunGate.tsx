"use client";

import { useState, type ReactNode } from "react";
import { motion } from "framer-motion";
import { agent } from "@/lib/agent-client";
import { useAppState } from "@/lib/app-state";
import {
  ConnectionFields,
  toPayload,
  useConnectionFields,
} from "@/components/dialogs/ConnectionFields";

/**
 * Mirrors the desktop startup flow (main._bootstrap): the main window is
 * ALWAYS shown, and when the app is not yet configured a SetupWizard is shown
 * as a modal on top of it. Skipping the wizard leaves the user in the app in
 * manual mode with an empty board — it never blocks access to the shell.
 */
export function FirstRunGate({ children }: { children: ReactNode }) {
  const { settings, setSettings } = useAppState();
  const [dismissed, setDismissed] = useState(false);

  const showWizard = !settings?.configured && !dismissed;

  return (
    <>
      {children}
      {showWizard && (
        <SetupWizard
          onConnected={(s) => setSettings(s)}
          onSkip={() => setDismissed(true)}
        />
      )}
    </>
  );
}

function SetupWizard({
  onConnected,
  onSkip,
}: {
  onConnected: (s: Awaited<ReturnType<typeof agent.getSettings>>) => void;
  onSkip: () => void;
}) {
  // Match the desktop first-run form: every field starts empty so the
  // Base URL shows its placeholder and is directly editable (the backend
  // supplies the default endpoint when none is submitted on save).
  const { values, setValues } = useConnectionFields();
  const [busy, setBusy] = useState(false);
  const [logs, setLogs] = useState<string[]>([]);
  const log = (m: string) => setLogs((p) => [...p, m]);

  const connect = async () => {
    if (!values.pat.trim() || !values.organization.trim()) {
      log("[ERROR] PAT and Organization are required.");
      return;
    }
    setBusy(true);
    setLogs([]);
    log("[INFO] Saving settings and connecting...");
    try {
      await agent.saveSettings(toPayload(values));
      const v = await agent.verifyPat();
      if (!v.ok) {
        log(`[ERROR] ADO connection failed: ${v.detail}`);
        setBusy(false);
        return;
      }
      log("[SUCCESS] ADO connected.");
      const s = await agent.getSettings();
      onConnected(s);
    } catch (e) {
      log(`[ERROR] Setup failed: ${(e as Error).message}`);
      setBusy(false);
    }
  };

  const skip = async () => {
    setBusy(true);
    try {
      await agent.saveSettings(toPayload(values));
    } catch {
      /* ignore — manual mode does not require valid credentials */
    }
    onSkip();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center overflow-auto bg-black/60 px-6 py-8">
      <motion.div
        initial={{ opacity: 0, scale: 0.97 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.2 }}
        className="tt-dialog w-full max-w-2xl p-7"
      >
        <h2 className="text-lg font-bold tracking-tight text-white">
          Testing Toolkit — one-time setup
        </h2>
        <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
          Enter your LLM API and Azure DevOps details. On{" "}
          <b className="text-[#bfc4cc]">Save &amp; Connect</b> the app stores
          credentials, verifies the PAT, and loads your projects. No API key?
          You can still proceed and use Manual Mode.
        </p>

        <div className="mt-5">
          <ConnectionFields values={values} setValues={setValues} />
        </div>

        {logs.length > 0 && (
          <div className="mt-4 max-h-28 overflow-auto rounded-lg border border-[#2d313c] bg-[#0d1017] p-3 font-mono text-xs">
            {logs.map((l, i) => (
              <div key={i} className="text-[#bfc4cc]">
                {l}
              </div>
            ))}
          </div>
        )}

        <div className="mt-6 flex justify-end gap-2">
          <button className="tt-btn-ghost" onClick={skip} disabled={busy}>
            Skip (manual mode)
          </button>
          <button
            className="tt-btn-success"
            onClick={connect}
            disabled={busy}
          >
            {busy ? "Connecting..." : "Save & Connect"}
          </button>
        </div>
      </motion.div>
    </div>
  );
}
