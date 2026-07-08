"use client";

/**
 * CoverageBar
 * A compact, single-row strip shown between ActionBar and BoardGrid that gives
 * the Senior QA engineer at-a-glance coverage and health metrics without
 * opening any dialog. Reads entirely from app-state — zero extra API calls.
 */

import { Layers, CheckSquare, TestTube2, PlayCircle, Clock } from "lucide-react";
import { useAppState } from "@/lib/app-state";

function timeSince(epochSec: number): string {
  const diffMs = Date.now() - epochSec * 1000;
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffH = Math.floor(diffMin / 60);
  if (diffH < 24) return `${diffH}h ago`;
  return `${Math.floor(diffH / 24)}d ago`;
}

export function CoverageBar() {
  const { boardView, selected, currentBoard, generateCtx } = useAppState();

  // Only render when a board is loaded
  if (!boardView) return null;

  const totalWi = boardView.rows.length;
  const selectedCount = selected.size;

  // generateCtx carries the last n_test_cases from the most recent generation
  // via the result stored in app-state. We surface what we have.
  // The E2ELastRun is not yet in app-state; CoverageBar shows TC stats from
  // generateCtx if available, otherwise omits that chip.
  const hasSelection = selectedCount > 0;

  return (
    <div
      className="flex shrink-0 items-center gap-1.5 border-b border-[var(--tt-outline-soft)] px-3 py-1 tt-animate-fade-up"
      style={{ background: "var(--tt-surface-deepest)" }}
      aria-label="Board coverage summary"
    >
      {/* Board label */}
      {currentBoard && (
        <span className="mr-1 truncate text-[10px] font-semibold uppercase tracking-wide text-[var(--tt-text-faint)]">
          {currentBoard.team_name}
        </span>
      )}

      {/* Work item count */}
      <span className="tt-metric-chip" title={`${totalWi} total work items on this board`}>
        <Layers className="h-3 w-3 text-[var(--tt-primary)]" />
        {totalWi} items
      </span>

      {/* Selection chip */}
      {hasSelection && (
        <span
          className="tt-metric-chip"
          style={{
            background: "rgba(91,168,255,0.10)",
            borderColor: "rgba(91,168,255,0.3)",
            color: "var(--tt-primary)",
          }}
          title={`${selectedCount} items selected for generation`}
        >
          <CheckSquare className="h-3 w-3" />
          {selectedCount} selected
        </span>
      )}

      {/* Type breakdown mini-pills */}
      <TypeBreakdown rows={boardView.rows} />

      <div className="flex-1" />

      {/* Last generation result (if ctx has it from this session) */}
      {generateCtx.tcType && (
        <span
          className="tt-metric-chip"
          style={{
            background: "rgba(26,171,92,0.10)",
            borderColor: "rgba(26,171,92,0.3)",
            color: "var(--tt-success)",
          }}
          title="Test cases generated this session"
        >
          <TestTube2 className="h-3 w-3" />
          TC generated
        </span>
      )}

      {/* Placeholder for E2E last run — wired when e2eLastRun enters app-state */}
      <span
        className="tt-metric-chip opacity-40"
        title="E2E last run — run E2E tests to see results here"
      >
        <PlayCircle className="h-3 w-3" />
        E2E ready
      </span>
    </div>
  );
}

/**
 * Shows up to 3 small type-count chips (User Story, Bug, Task) without taking
 * too much horizontal space.
 */
function TypeBreakdown({
  rows,
}: {
  rows: { wi_type: string }[];
}) {
  if (!rows.length) return null;

  // Count by normalized type key
  const counts: Record<string, number> = {};
  for (const r of rows) {
    const k = normalizeType(r.wi_type);
    counts[k] = (counts[k] ?? 0) + 1;
  }

  const ORDER = ["story", "bug", "task", "epic", "feature", "other"];
  const TYPE_COLOR: Record<string, string> = {
    story:   "var(--tt-type-story)",
    bug:     "var(--tt-type-bug)",
    task:    "var(--tt-type-task)",
    epic:    "var(--tt-type-epic)",
    feature: "var(--tt-type-feature)",
    other:   "var(--tt-text-muted)",
  };
  const TYPE_BG: Record<string, string> = {
    story:   "var(--tt-type-story-bg)",
    bug:     "var(--tt-type-bug-bg)",
    task:    "var(--tt-type-task-bg)",
    epic:    "var(--tt-type-epic-bg)",
    feature: "var(--tt-type-feature-bg)",
    other:   "rgba(138,143,153,0.10)",
  };
  const TYPE_LABEL: Record<string, string> = {
    story: "Story",
    bug: "Bug",
    task: "Task",
    epic: "Epic",
    feature: "Feature",
    other: "Other",
  };

  return (
    <>
      {ORDER.filter((k) => counts[k] > 0)
        .slice(0, 4)
        .map((k) => (
          <span
            key={k}
            className="tt-metric-chip"
            style={{
              background: TYPE_BG[k],
              borderColor: TYPE_COLOR[k] + "44",
              color: TYPE_COLOR[k],
            }}
            title={`${counts[k]} ${TYPE_LABEL[k]} work item${counts[k] === 1 ? "" : "s"}`}
          >
            <span
              className="tt-chip-dot"
              style={{ background: TYPE_COLOR[k] }}
            />
            {counts[k]} {TYPE_LABEL[k]}
          </span>
        ))}
    </>
  );
}

function normalizeType(t: string): string {
  const k = (t || "").toLowerCase();
  if (k.includes("story") || k.includes("user story")) return "story";
  if (k.includes("bug") || k.includes("issue")) return "bug";
  if (k.includes("task")) return "task";
  if (k.includes("epic")) return "epic";
  if (k.includes("feature")) return "feature";
  return "other";
}
