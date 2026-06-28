import {
  setPendingReinstallPref,
  setTourCompletedPref,
  setPendingReindexPref,
} from "./preferences";

/**
 * Kick off a full reinstall and reload into the Step 1 installer (onboarding).
 *
 * A reinstall means re-downloading and re-running the installer, which is also
 * the only way to recover an install whose agent can't self-update. We persist
 * the intentions so they survive the reload:
 *   - pendingReinstall: force the installer download/run screen (app/page.tsx).
 *   - tourCompleted=false: run the quick tour again afterwards.
 *   - pendingReindex: rebuild every KB once the fresh agent reconnects.
 * Settings, fetched models, preferences and generated artifacts are retained;
 * the fresh install clears transient caches and the reindex rebuilds vectors.
 */
export function requestReinstall() {
  setPendingReinstallPref(true);
  setTourCompletedPref(false);
  setPendingReindexPref(true);
  if (typeof window !== "undefined") window.location.reload();
}
