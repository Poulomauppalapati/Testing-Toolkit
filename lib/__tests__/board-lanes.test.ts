import { describe, it, expect, beforeEach, vi } from "vitest";

// Minimal localStorage stub so the module's persistence works under vitest.
function installLocalStorage() {
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

describe("board-lanes collapse store", () => {
  let store: Map<string, string>;

  beforeEach(async () => {
    vi.resetModules();
    store = installLocalStorage();
  });

  it("toggles a lane collapsed and persists it", async () => {
    const { toggleLaneCollapsed } = await import("../board-lanes");
    toggleLaneCollapsed("NEW");
    const raw = JSON.parse(store.get("tt.board.lanes.v1") ?? "[]");
    expect(raw).toContain("NEW");
    // Toggling again expands (removes) it.
    toggleLaneCollapsed("NEW");
    expect(JSON.parse(store.get("tt.board.lanes.v1") ?? "[]")).not.toContain(
      "NEW"
    );
  });

  it("collapses and expands all provided lanes", async () => {
    const { setAllLanesCollapsed } = await import("../board-lanes");
    setAllLanesCollapsed(["NEW", "BACKLOG", "DONE"], true);
    expect(JSON.parse(store.get("tt.board.lanes.v1") ?? "[]").sort()).toEqual([
      "BACKLOG",
      "DONE",
      "NEW",
    ]);
    setAllLanesCollapsed(["NEW", "BACKLOG", "DONE"], false);
    expect(JSON.parse(store.get("tt.board.lanes.v1") ?? "[]")).toEqual([]);
  });

  it("restores persisted collapsed lanes across reload", async () => {
    store.set("tt.board.lanes.v1", JSON.stringify(["IN DEVELOPMENT"]));
    const { toggleLaneCollapsed } = await import("../board-lanes");
    // A no-op-adjacent toggle on a different lane should keep the restored one.
    toggleLaneCollapsed("NEW");
    const raw = JSON.parse(store.get("tt.board.lanes.v1") ?? "[]");
    expect(raw).toContain("IN DEVELOPMENT");
    expect(raw).toContain("NEW");
  });
});
