"use client";

/**
 * use-web-freshness.ts
 * Keeps the WEB app itself current. The web app is the orchestrator that decides
 * whether the agent is up to date, so a stale frontend (a long-open tab running
 * an old bundle) would undermine every other guarantee. This hook periodically
 * asks the server for the currently-deployed build id and, when it differs from
 * the build id baked into this running bundle, reloads the page to pick up the
 * new deployment. It also re-checks when the tab regains focus or the network
 * comes back online.
 */

import { useCallback, useEffect, useRef } from "react";

const OWN_BUILD_ID = process.env.NEXT_PUBLIC_BUILD_ID || "dev";
const POLL_MS = 5 * 60 * 1000; // every 5 minutes while open

async function fetchDeployedBuildId(): Promise<string | null> {
  try {
    const res = await fetch("/api/build-id", { cache: "no-store" });
    if (!res.ok) return null;
    const data = (await res.json()) as { buildId?: string };
    return data.buildId ?? null;
  } catch {
    return null;
  }
}

export function useWebFreshness() {
  // Guard so we only ever trigger one reload.
  const reloadingRef = useRef(false);

  const checkAndReload = useCallback(async () => {
    if (reloadingRef.current) return;
    const deployed = await fetchDeployedBuildId();
    if (!deployed) return; // can't verify -> do nothing (fail safe, no churn)
    // "dev" locally won't match a real SHA; only reload when we have a real id
    // baked in and it differs from what's deployed.
    if (OWN_BUILD_ID === "dev") return;
    if (deployed !== OWN_BUILD_ID) {
      reloadingRef.current = true;
      // Hard reload to bypass any cached shell.
      if (typeof window !== "undefined") window.location.reload();
    }
  }, []);

  useEffect(() => {
    // Check shortly after mount, then on an interval.
    const initial = setTimeout(checkAndReload, 2000);
    const interval = setInterval(checkAndReload, POLL_MS);

    const onFocus = () => void checkAndReload();
    const onOnline = () => void checkAndReload();
    window.addEventListener("focus", onFocus);
    window.addEventListener("online", onOnline);

    return () => {
      clearTimeout(initial);
      clearInterval(interval);
      window.removeEventListener("focus", onFocus);
      window.removeEventListener("online", onOnline);
    };
  }, [checkAndReload]);
}
