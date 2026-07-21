"use client";

/**
 * board-columns.ts
 * localStorage-backed state for the work-item grid's columns:
 *   - per-column pixel width (Excel-like drag-to-resize), and
 *   - per-column collapsed flag (click the header caret to hide/show a column).
 *
 * State is global (the column set is fixed) and persisted immediately on every
 * commit so the layout the user left behind is restored automatically on the
 * next launch. Live resize drags update the in-memory value continuously and
 * flush to disk only on pointer-up to avoid hammering localStorage.
 */

import { useCallback, useSyncExternalStore } from "react";

/** Stable identifiers for every resizable/collapsible grid column. The leading
 * checkbox column is intentionally excluded (fixed width, always visible). */
export type BoardColumnId =
  | "id"
  | "title"
  | "type"
  | "state"
  | "assignee"
  | "sprint"
  | "tests";

export interface BoardColumnMeta {
  id: BoardColumnId;
  label: string;
  /** Default pixel width. */
  width: number;
  /** Minimum pixel width when resizing. */
  min: number;
}

/** Column order + defaults (matches the desktop board layout). */
export const BOARD_COLUMNS: readonly BoardColumnMeta[] = [
  { id: "id", label: "ID", width: 90, min: 60 },
  { id: "title", label: "Title", width: 380, min: 160 },
  { id: "type", label: "Type", width: 110, min: 80 },
  { id: "state", label: "State", width: 140, min: 90 },
  { id: "assignee", label: "Assignee", width: 140, min: 90 },
  { id: "sprint", label: "Sprint", width: 150, min: 90 },
  { id: "tests", label: "Generated Tests", width: 120, min: 90 },
] as const;

/** Pixel width of a collapsed column (just enough for the expand caret). */
export const COLLAPSED_WIDTH = 30;

/** Available row fields that can be mapped to any column cell. */
export type RowField =
  | "wi_id"
  | "title"
  | "wi_type"
  | "state"
  | "board_column"
  | "board_lane"
  | "assigned_to"
  | "tags"
  | "iteration_path"
  | "iteration_leaf"
  | "area_path"
  | "linked_test_case_count"
  | "created_date";

/** Default field each column shows when no user override exists. */
export const DEFAULT_FIELD_MAP: Record<BoardColumnId, RowField> = {
  id: "wi_id",
  title: "title",
  type: "wi_type",
  state: "state",
  assignee: "assigned_to",
  sprint: "board_lane",
  tests: "linked_test_case_count",
};

/** Human-friendly labels for row fields shown in the context menu. */
export const FIELD_LABELS: Record<RowField, string> = {
  wi_id: "ID",
  title: "Title",
  wi_type: "Type",
  state: "State",
  board_column: "Board Column",
  board_lane: "Board Lane / Sprint",
  assigned_to: "Assignee",
  tags: "Tags",
  iteration_path: "Iteration Path",
  iteration_leaf: "Iteration (leaf)",
  area_path: "Area Path",
  linked_test_case_count: "Linked Test Cases",
  created_date: "Created Date",
};

interface ColumnState {
  widths: Partial<Record<BoardColumnId, number>>;
  collapsed: Partial<Record<BoardColumnId, boolean>>;
  fieldMap: Partial<Record<BoardColumnId, RowField>>;
}

const KEY = "tt.board.columns.v1";

const DEFAULTS: ColumnState = { widths: {}, collapsed: {}, fieldMap: {} };

let cache: ColumnState = DEFAULTS;
let loaded = false;
const listeners = new Set<() => void>();

const VALID_IDS = new Set<string>(BOARD_COLUMNS.map((c) => c.id));

const VALID_FIELDS = new Set<string>(Object.keys(FIELD_LABELS));

function load(): ColumnState {
  if (typeof window === "undefined") return DEFAULTS;
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return DEFAULTS;
    const parsed = JSON.parse(raw) as Partial<ColumnState>;
    const widths: Partial<Record<BoardColumnId, number>> = {};
    const collapsed: Partial<Record<BoardColumnId, boolean>> = {};
    const fieldMap: Partial<Record<BoardColumnId, RowField>> = {};
    for (const [k, v] of Object.entries(parsed.widths ?? {})) {
      if (VALID_IDS.has(k) && typeof v === "number" && v > 0)
        widths[k as BoardColumnId] = v;
    }
    for (const [k, v] of Object.entries(parsed.collapsed ?? {})) {
      if (VALID_IDS.has(k) && v === true) collapsed[k as BoardColumnId] = true;
    }
    for (const [k, v] of Object.entries(parsed.fieldMap ?? {})) {
      if (VALID_IDS.has(k) && typeof v === "string" && VALID_FIELDS.has(v))
        fieldMap[k as BoardColumnId] = v as RowField;
    }
    return { widths, collapsed, fieldMap };
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

function persist(next: ColumnState, write = true) {
  cache = next;
  if (write && typeof window !== "undefined") {
    try {
      window.localStorage.setItem(KEY, JSON.stringify(next));
    } catch {
      /* storage unavailable (private mode) — keep in-memory copy */
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

function getSnapshot(): ColumnState {
  ensureLoaded();
  return cache;
}

function getServerSnapshot(): ColumnState {
  return DEFAULTS;
}

const META_BY_ID = new Map<BoardColumnId, BoardColumnMeta>(
  BOARD_COLUMNS.map((c) => [c.id, c])
);

/** Effective width for a column (collapsed → COLLAPSED_WIDTH). */
export function columnWidth(state: ColumnState, id: BoardColumnId): number {
  if (state.collapsed[id]) return COLLAPSED_WIDTH;
  return state.widths[id] ?? META_BY_ID.get(id)?.width ?? 120;
}

/**
 * Responsive auto-fit: distribute available width proportionally across all
 * non-collapsed columns. Runs on every container resize (nav, logs, detail
 * pane open/close, window resize) so columns always fill the viewport.
 *
 * Manual drag-resize sets a "pinned" width for that column; pinned columns
 * keep their width and remaining space distributes among unpinned columns.
 * Calling resetBoardColumns() clears all pins.
 */
let manuallyResized = new Set<BoardColumnId>();

export function autofitColumns(containerWidth: number): void {
  ensureLoaded();
  if (containerWidth <= 0) return;
  const CHECKBOX_COL = 32;
  const available = containerWidth - CHECKBOX_COL;

  // Pinned columns (manually resized this session) keep their width.
  let pinnedTotal = 0;
  for (const c of BOARD_COLUMNS) {
    if (cache.collapsed[c.id]) {
      pinnedTotal += COLLAPSED_WIDTH;
    } else if (manuallyResized.has(c.id)) {
      pinnedTotal += cache.widths[c.id] ?? c.width;
    }
  }

  const unpinned = BOARD_COLUMNS.filter(
    (c) => !cache.collapsed[c.id] && !manuallyResized.has(c.id)
  );
  const unpinnedDefault = unpinned.reduce((s, c) => s + c.width, 0);
  const space = available - pinnedTotal;
  if (space <= 0 || unpinnedDefault <= 0) return;

  const scale = space / unpinnedDefault;
  const widths: Partial<Record<BoardColumnId, number>> = { ...cache.widths };
  for (const c of unpinned) {
    widths[c.id] = Math.max(c.min, Math.round(c.width * scale));
  }
  persist({ ...cache, widths }, false);
}

/** Non-hook setter for a column width. Pass write=false during a live drag. */
function setColumnWidth(id: BoardColumnId, px: number, write = true) {
  ensureLoaded();
  const min = META_BY_ID.get(id)?.min ?? 60;
  const clamped = Math.max(min, Math.round(px));
  if (write) manuallyResized.add(id);
  persist(
    { ...cache, widths: { ...cache.widths, [id]: clamped } },
    write
  );
}

/** Change which row field a column displays. */
function setColumnField(id: BoardColumnId, field: RowField) {
  ensureLoaded();
  persist({ ...cache, fieldMap: { ...cache.fieldMap, [id]: field } });
}

/** Non-hook toggle for a column's collapsed flag (always persisted). */
function toggleColumnCollapsed(id: BoardColumnId) {
  ensureLoaded();
  const next = !cache.collapsed[id];
  persist({
    ...cache,
    collapsed: { ...cache.collapsed, [id]: next },
  });
}

/** Reset all columns to their default widths, expand, and clear field overrides. */
export function resetBoardColumns() {
  manuallyResized = new Set();
  persist({ widths: {}, collapsed: {}, fieldMap: {} });
}

/** Resolve which row field a column is currently displaying. */
export function columnField(state: ColumnState, id: BoardColumnId): RowField {
  return state.fieldMap[id] ?? DEFAULT_FIELD_MAP[id];
}

export function useBoardColumns() {
  const state = useSyncExternalStore(
    subscribe,
    getSnapshot,
    getServerSnapshot
  );

  const width = useCallback(
    (id: BoardColumnId) => columnWidth(state, id),
    [state]
  );
  const isCollapsed = useCallback(
    (id: BoardColumnId) => !!state.collapsed[id],
    [state]
  );
  const fieldFor = useCallback(
    (id: BoardColumnId) => columnField(state, id),
    [state]
  );

  return {
    state,
    width,
    isCollapsed,
    fieldFor,
    setWidth: setColumnWidth,
    setField: setColumnField,
    toggleCollapsed: toggleColumnCollapsed,
    reset: resetBoardColumns,
    autofit: autofitColumns,
  };
}
