"use client";

import {
  Zap,
  FlaskConical,
  ClipboardCheck,
  Package,
  Upload,
  Bug,
  SearchCode,
  Sparkles,
  KeyRound,
  PlayCircle,
  PanelBottomOpen,
  PanelBottomClose,
  CheckSquare,
  Layers,
} from "lucide-react";
import { TC_TYPES, TC_BUTTON_LABEL, type TcType } from "@/lib/agent-client";
import { useAppState } from "@/lib/app-state";

const TC_ICON: Record<TcType, React.ReactNode> = {
  implementation: <Zap className="h-3.5 w-3.5 shrink-0" />,
  sit: <FlaskConical className="h-3.5 w-3.5 shrink-0" />,
  uat: <ClipboardCheck className="h-3.5 w-3.5 shrink-0" />,
};

const TC_COLOR: Record<TcType, string> = {
  implementation: "var(--tt-type-story)",
  sit: "var(--tt-type-epic)",
  uat: "var(--tt-type-feature)",
};

export function ActionBar() {
  const {
    selected,
    currentProject,
    boardView,
    openDialog,
    setGenerateCtx,
    logVisible,
    setLogVisible,
  } = useAppState();

  const count = selected.size;
  const hasSelection = count > 0;
  const hasProject = !!currentProject;
  const totalRows = boardView?.rows.length ?? 0;

  return (
    <div
      className="flex items-center gap-0 px-3 py-1.5 shrink-0 border-b border-[var(--tt-outline-soft)]"
      style={{ background: "var(--tt-surface-deepest)" }}
    >
      {/* ── GROUP 1: Generate ────────────────────────────────────── */}
      <div className="tt-action-group" aria-label="Generate test cases">
        {TC_TYPES.map((t) => (
          <button
            key={t}
            className="tt-btn-ghost !px-2.5 !py-1 !text-xs !gap-1.5 !rounded-lg"
            style={
              hasSelection
                ? { color: TC_COLOR[t] }
                : undefined
            }
            disabled={!hasSelection}
            title={`Generate ${TC_BUTTON_LABEL[t]} test cases for selected work items`}
            onClick={() => {
              setGenerateCtx({ tcType: t });
              openDialog("generate");
            }}
          >
            {TC_ICON[t]}
            <span>{TC_BUTTON_LABEL[t]}</span>
          </button>
        ))}
      </div>

      <div className="tt-action-sep" />

      {/* ── GROUP 2: Publish ─────────────────────────────────────── */}
      <div className="tt-action-group" aria-label="Publish outputs">
        <button
          className="tt-btn-ghost !px-2.5 !py-1 !text-xs !gap-1.5 !rounded-lg"
          title="Bundle the ticked work items into PDFs, or open the PDF Packager if no items are selected"
          onClick={() => openDialog("package")}
        >
          <Package className="h-3.5 w-3.5 shrink-0" />
          <span>Package PDFs</span>
        </button>
        <button
          className="tt-btn-ghost !px-2.5 !py-1 !text-xs !gap-1.5 !rounded-lg"
          disabled={!hasProject}
          title="Push reviewed test cases to ADO"
          onClick={() => openDialog("upload")}
        >
          <Upload className="h-3.5 w-3.5 shrink-0" />
          <span>Upload to ADO</span>
        </button>
        <button
          className="tt-btn-ghost !px-2.5 !py-1 !text-xs !gap-1.5 !rounded-lg"
          style={hasProject ? { color: "var(--tt-type-bug)" } : undefined}
          disabled={!hasProject}
          title="Parse defect documents and create Bug work items in ADO"
          onClick={() => openDialog("defect")}
        >
          <Bug className="h-3.5 w-3.5 shrink-0" />
          <span>Defect Upload</span>
        </button>
      </div>

      <div className="tt-action-sep" />

      {/* ── GROUP 3: Tools ───────────────────────────────────────── */}
      <div className="tt-action-group" aria-label="Tools">
        <button
          className="tt-btn-ghost !px-2.5 !py-1 !text-xs !gap-1.5 !rounded-lg"
          disabled={!hasProject}
          title="Preview which KB chunks the retriever would supply for a story"
          onClick={() => openDialog("retrieval")}
        >
          <SearchCode className="h-3.5 w-3.5 shrink-0" />
          <span>Retrieval</span>
        </button>
        <button
          className="tt-btn-ghost !px-2.5 !py-1 !text-xs !gap-1.5 !rounded-lg"
          style={hasProject ? { color: "var(--tt-warn)" } : undefined}
          disabled={!hasProject}
          title="Chat with the assistant — search, read, update, and create ADO work items with KB grounding"
          onClick={() => openDialog("chat")}
        >
          <Sparkles className="h-3.5 w-3.5 shrink-0" />
          <span>Custom Generate</span>
        </button>
        <button
          className="tt-btn-ghost !px-2.5 !py-1 !text-xs !gap-1.5 !rounded-lg"
          disabled={!hasProject}
          title="Manage encrypted test-environment credentials for E2E automation"
          onClick={() => openDialog("credentials")}
        >
          <KeyRound className="h-3.5 w-3.5 shrink-0" />
          <span>Credentials</span>
        </button>
        <button
          className="tt-btn-ghost !px-2.5 !py-1 !text-xs !gap-1.5 !rounded-lg"
          style={hasProject ? { color: "var(--tt-success)" } : undefined}
          disabled={!hasProject}
          title="Run generated test cases in a real browser with Playwright and capture screenshots"
          onClick={() => openDialog("e2e")}
        >
          <PlayCircle className="h-3.5 w-3.5 shrink-0" />
          <span>Run E2E</span>
        </button>
      </div>

      {/* ── Spacer ───────────────────────────────────────────────── */}
      <div className="flex-1" />

      {/* ── Selection / board stats ──────────────────────────────── */}
      {hasProject && (
        <div className="flex items-center gap-2 mr-2">
          {hasSelection ? (
            <span className="tt-badge tt-badge-info tt-animate-badge-pop">
              <CheckSquare className="h-3 w-3" />
              {count}&nbsp;selected
            </span>
          ) : totalRows > 0 ? (
            <span className="tt-badge tt-badge-neutral">
              <Layers className="h-3 w-3" />
              {totalRows}&nbsp;items
            </span>
          ) : null}
        </div>
      )}

      {/* ── Log toggle ───────────────────────────────────────────── */}
      <button
        className="tt-btn-ghost !px-2 !py-1 !text-xs shrink-0"
        onClick={() => setLogVisible(!logVisible)}
        title={logVisible ? "Hide activity log" : "Show activity log"}
        aria-label={logVisible ? "Hide log" : "Show log"}
      >
        {logVisible ? (
          <PanelBottomClose className="h-3.5 w-3.5" />
        ) : (
          <PanelBottomOpen className="h-3.5 w-3.5" />
        )}
      </button>
    </div>
  );
}
