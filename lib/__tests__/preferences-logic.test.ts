import { describe, it, expect, beforeEach, vi } from "vitest";

// Minimal localStorage stub (same pattern as board-lanes.test.ts).
function installLocalStorage(): Map<string, string> {
  const store = new Map<string, string>();
  const ls = {
    getItem: (k: string) => (store.has(k) ? store.get(k)! : null),
    setItem: (k: string, v: string) => void store.set(k, String(v)),
    removeItem: (k: string) => void store.delete(k),
    clear: () => store.clear(),
  };
  vi.stubGlobal("window", { localStorage: ls });
  vi.stubGlobal("localStorage", ls);
  return store;
}

describe("todayKey", () => {
  beforeEach(() => {
    vi.resetModules();
    installLocalStorage();
  });

  it("returns a YYYY-MM-DD string matching today's local date", async () => {
    const { todayKey } = await import("../preferences");
    const key = todayKey();
    // Matches YYYY-MM-DD format
    expect(key).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    // Matches today's date
    const now = new Date();
    const expected = [
      String(now.getFullYear()),
      String(now.getMonth() + 1).padStart(2, "0"),
      String(now.getDate()).padStart(2, "0"),
    ].join("-");
    expect(key).toBe(expected);
  });
});

describe("isFirstLaunchToday", () => {
  beforeEach(() => {
    vi.resetModules();
    installLocalStorage();
  });

  it("returns true when localStorage lacks today's key", async () => {
    const { isFirstLaunchToday } = await import("../preferences");
    expect(isFirstLaunchToday()).toBe(true);
  });

  it("returns false when lastUpdateCheck matches today", async () => {
    const store = installLocalStorage();
    const now = new Date();
    const today = [
      String(now.getFullYear()),
      String(now.getMonth() + 1).padStart(2, "0"),
      String(now.getDate()).padStart(2, "0"),
    ].join("-");
    store.set(
      "tt.ui.prefs.v3",
      JSON.stringify({ lastUpdateCheck: today })
    );
    const { isFirstLaunchToday } = await import("../preferences");
    expect(isFirstLaunchToday()).toBe(false);
  });
});

describe("markUpdateCheckedToday", () => {
  let store: Map<string, string>;

  beforeEach(() => {
    vi.resetModules();
    store = installLocalStorage();
  });

  it("sets a flag that isFirstLaunchToday detects", async () => {
    const { markUpdateCheckedToday, isFirstLaunchToday } = await import(
      "../preferences"
    );
    expect(isFirstLaunchToday()).toBe(true);
    markUpdateCheckedToday();
    expect(isFirstLaunchToday()).toBe(false);
    // Verify raw storage was written
    const raw = JSON.parse(store.get("tt.ui.prefs.v3") ?? "{}");
    expect(raw.lastUpdateCheck).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });
});

describe("getPreferences", () => {
  beforeEach(() => {
    vi.resetModules();
    installLocalStorage();
  });

  it("returns default object when localStorage is empty", async () => {
    const { getPreferences } = await import("../preferences");
    const prefs = getPreferences();
    expect(prefs.theme).toBe("dark");
    expect(prefs.panels).toEqual({ nav: true, detail: true, log: false });
    expect(prefs.sizes).toEqual({
      navWidth: 224,
      detailWidth: 440,
      logHeight: 180,
    });
    expect(prefs.pendingReindex).toBe(false);
    expect(prefs.pendingReinstall).toBe(false);
    expect(prefs.lastUpdateCheck).toBe("");
    expect(prefs.lastProject).toBe("");
    expect(prefs.lastBoard).toBe("");
  });
});
