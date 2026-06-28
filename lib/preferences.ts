"use client";

/**
 * preferences.ts
 * Small localStorage-backed store for persistent UI preferences (which nav
 * sections are collapsed, whether the first-run guided tour was completed).
 *
 * Every mutation is written to localStorage immediately so the layout the user
 * left behind is restored verbatim on the next launch. Uses
 * useSyncExternalStore so multiple components (NavPanel, ActivityBar, the tour)
 * stay in sync and SSR/hydration is handled without warnings.
 */

import { useCallback, useSyncExternalStore } from "react";

export type SectionKey = "update" | "projects" | "boards";

export interface UiPreferences {
  /** true = collapsed/hidden. First launch defaults everything to collapsed. */
  sections: Record<SectionKey, boolean>;
  /** true once the user has finished (or skipped) the guided tour. */
  tourCompleted: boolean;
}

const KEY = "tt.ui.prefs.v1";

// First-time launch: every collapsible section starts collapsed/hidden and the
// tour has not run yet.
const DEFAULTS: UiPreferences = {
  sections: { update: true, projects: true, boards: true },
  tourCompleted: false,
};

let cache: UiPreferences = DEFAULTS;
let loaded = false;
const listeners = new Set<() => void>();

function load(): UiPreferences {
  if (typeof window === "undefined") return DEFAULTS;
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return DEFAULTS;
    const parsed = JSON.parse(raw) as Partial<UiPreferences>;
    return {
      sections: { ...DEFAULTS.sections, ...(parsed.sections ?? {}) },
      tourCompleted: !!parsed.tourCompleted,
    };
  } catch {
    return DEFAULTS;
  }
}

function ensureLoaded() {
  if (!loaded) {
    cache = load();
    loaded = true;
  }
}

function persist(next: UiPreferences) {
  cache = next;
  if (typeof window !== "undefined") {
    try {
      window.localStorage.setItem(KEY, JSON.stringify(next));
    } catch {
      /* storage may be unavailable (private mode) — keep in-memory copy */
    }
  }
  for (const l of listeners) l();
}

function subscribe(cb: () => void): () => void {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
}

function getSnapshot(): UiPreferences {
  ensureLoaded();
  return cache;
}

function getServerSnapshot(): UiPreferences {
  return DEFAULTS;
}

export function usePreferences() {
  const prefs = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

  const setSectionCollapsed = useCallback(
    (key: SectionKey, collapsed: boolean) => {
      ensureLoaded();
      persist({
        ...cache,
        sections: { ...cache.sections, [key]: collapsed },
      });
    },
    []
  );

  const toggleSection = useCallback((key: SectionKey) => {
    ensureLoaded();
    persist({
      ...cache,
      sections: { ...cache.sections, [key]: !cache.sections[key] },
    });
  }, []);

  const setTourCompleted = useCallback((value: boolean) => {
    ensureLoaded();
    persist({ ...cache, tourCompleted: value });
  }, []);

  return { prefs, setSectionCollapsed, toggleSection, setTourCompleted };
}
