import { setPendingReinstallPref } from "./preferences";

export type ReinstallReason = "update" | "reinstall";

const REASON_KEY = "tt.reinstall.reason";

export function getReinstallReason(): ReinstallReason {
  if (typeof window === "undefined") return "reinstall";
  return (window.localStorage.getItem(REASON_KEY) as ReinstallReason) || "reinstall";
}

function setReinstallReason(reason: ReinstallReason) {
  if (typeof window !== "undefined") {
    window.localStorage.setItem(REASON_KEY, reason);
  }
}

export function clearReinstallReason() {
  if (typeof window !== "undefined") {
    window.localStorage.removeItem(REASON_KEY);
  }
}

/**
 * Enter the fresh-installer flow without resetting user state.
 *
 * The installer refreshes the local agent binaries and transient distribution
 * cache. Existing connection settings, credentials, generated artifacts, UI
 * preferences, and selected project/board are preserved.
 * Normal KB currency checks decide whether any index needs rebuilding.
 */
export function requestReinstall(reason: ReinstallReason = "reinstall") {
  setReinstallReason(reason);
  setPendingReinstallPref(true);
  if (typeof window !== "undefined") window.location.reload();
}
