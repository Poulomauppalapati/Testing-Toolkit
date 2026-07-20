"use client";

import { useState } from "react";
import { RefreshCw, LayoutDashboard, Download } from "lucide-react";

import { useAppState } from "@/lib/app-state";
import { useTheme } from "@/lib/theme";
import { Dropdown } from "@/components/ui/dropdown";
import { agent, type Board } from "@/lib/agent-client";
import { getPreferences, setSizePref } from "@/lib/preferences";
import { exportAllBoards } from "@/lib/export-board";
import { showToast } from "@/lib/toast";
import { ResizeHandle } from "@/components/ui/resizer";
import { useAppUpdate } from "@/lib/use-app-update";
import { SourceLogo } from "@/components/ui/source-logo";
import { projectSourceType } from "@/lib/board-utils";

export function NavPanel({ hidden }: { hidden?: boolean } = {}) {
  const {
    projects,
    currentProject,
    selectProject,
    reloadProjects,
    displayName,
    boards,
    currentBoard,
    selectBoard,
    reloadBoards,
    setNavVisible,
    openDialog,
    setLogVisible,
    pushLog,
    settings,
  } = useAppState();

  const { theme, toggleTheme } = useTheme();
  const { check: checkForUpdate, busy: updateBusy } = useAppUpdate(pushLog);
  const [width, setWidth] = useState(() => getPreferences().sizes.navWidth);
  const [exportingAll, setExportingAll] = useState(false);
  const [exportAllProgress, setExportAllProgress] = useState("");

  async function fetchBoardWithDegradationCheck(
    proj: string,
    board: Board,
    projName: string,
    boardName: string,
    opts?: { timeoutMs?: number },
  ): Promise<import("@/lib/agent-client").WorkItemRow[]> {
    let view = await agent.boardView(proj, board, {
      timeoutMs: opts?.timeoutMs,
      scopeToTeamArea: true,
    });
    if (view.possibly_degraded && (view.rows ?? []).length === 0) {
      pushLog("WARN", `${boardName} in ${projName}: ADO returned empty results (suspected throttling) — retrying after 8s...`);
      await new Promise(r => setTimeout(r, 8000));
      view = await agent.boardView(proj, board, {
        timeoutMs: opts?.timeoutMs,
        scopeToTeamArea: true,
      });
    }
    const rows = (view.rows ?? []).filter((r) => r && r.wi_id != null);
    if (rows.length === 0) {
      if (view.possibly_degraded) {
        pushLog("ERROR", `${boardName} in ${projName} returned 0 rows after retry — ADO is likely throttling this board's query. This is NOT an empty board.`);
      } else {
        pushLog("WARN", `${boardName} in ${projName} returned 0 valid rows — skipped (genuinely empty board).`);
      }
    }
    return rows;
  }

  async function onExportAllBoards() {
    if (!currentProject || boards.length === 0) return;
    setExportingAll(true);
    setExportAllProgress(`0/${boards.length} boards`);
    pushLog("INFO", `Exporting ${boards.length} board(s) to Excel...`);
    try {
      const results: Array<{ board: Board; rows: import("@/lib/agent-client").WorkItemRow[] }> = [];
      const projName = displayName(currentProject);
      for (let i = 0; i < boards.length; i++) {
        const b = boards[i];
        const name = b.team_name || b.name || b.label;
        setExportAllProgress(`${i + 1}/${boards.length}: ${name}`);
        try {
          const rows = await fetchBoardWithDegradationCheck(currentProject, b, projName, name);
          if (rows.length > 0) {
            results.push({ board: b, rows });
          }
        } catch (err) {
          pushLog("ERROR", `Skipped ${name} in ${projName} (fetch error: ${(err as Error).message || String(err)})`);
        }
      }
      setExportAllProgress("Building workbook...");
      await exportAllBoards({
        projectName: projName,
        boards: results,
        settings,
      });
      pushLog("SUCCESS", `Exported ${boards.length} board(s) from ${projName} to Excel.`);
      showToast(`Exported ${boards.length} board(s) from ${projName} to Excel`);
    } catch (e) {
      pushLog("ERROR", `Export failed: ${(e as Error).message}`);
    } finally {
      setExportingAll(false);
      setExportAllProgress("");
    }
  }

  async function onUpdateClick() {
    setLogVisible(true);
    await checkForUpdate();
  }

  async function openLogFolder() {
    setLogVisible(true);
    try {
      const res = await agent.openLogFolder();
      if (res.ok) {
        pushLog("INFO", `Opened log folder: ${res.detail}`);
      } else {
        pushLog("WARN", `Could not open log folder: ${res.detail}`);
      }
    } catch (e) {
      pushLog("WARN", `Could not open log folder: ${(e as Error).message}`);
    }
  }

  return (
    <div style={hidden ? { display: "none" } : { display: "contents" }}>
      <div
        className="tt-rail flex shrink-0 flex-col gap-3 p-2"
        style={{ width }}
      >
        {/* ── Projects ───────────────────────────────────────────── */}
        <div className="flex min-h-0 flex-1 flex-col">
          <div className="flex items-center justify-between px-1 pb-1.5">
            <span className="tt-section-header shrink-0">Projects</span>
            <button
              className="tt-btn-ghost shrink-0 !px-1.5 !py-0.5 !text-[10px] !gap-1"
              onClick={reloadProjects}
              title="Refresh project list"
            >
              <RefreshCw className="h-2.5 w-2.5" />
              Refresh
            </button>
          </div>
          <div className="min-h-[60px] flex-1 overflow-auto rounded-[8px] border border-[var(--tt-outline-soft)] bg-[var(--tt-surface-base)] p-1">
            {projects.length === 0 ? (
              <p className="px-2 py-2 text-xs text-muted-foreground">
                No projects. Connect Azure DevOps or JIRA in Settings.
              </p>
            ) : (
              projects.map((full) => {
                const name = displayName(full);
                const isSelected = full === currentProject;
                const source = projectSourceType(full, {
                  jiraConfigured: settings?.jira_configured,
                  adoConfigured: settings?.ado_configured,
                });
                return (
                  <div
                    key={full}
                    role="button"
                    tabIndex={0}
                    data-selected={isSelected}
                    onClick={() => selectProject(full)}
                    onKeyDown={(e) => {
                      // ARIA button pattern: activate on Enter and Space.
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        selectProject(full);
                      }
                    }}
                    className="tt-list-item flex items-center gap-2 text-sm"
                    title={full}
                  >
                    {/* Work-item source brand mark (Azure DevOps / Jira) */}
                    <SourceLogo source={source} size={18} />
                    <span className="truncate">{name}</span>
                    {isSelected && (
                      <LayoutDashboard className="ml-auto h-3 w-3 shrink-0 opacity-60" />
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* ── Boards ─────────────────────────────────────────────── */}
        <div className="flex min-h-0 flex-1 flex-col">
          <div className="flex items-center justify-between px-1 pb-1.5">
            <span className="tt-section-header shrink-0">Boards</span>
            <div className="flex min-w-0 items-center gap-1">
              <button
                className="tt-btn-ghost flex min-w-0 items-center justify-center !p-0 gap-1"
                style={{ height: 20, minWidth: 20, paddingInline: exportAllProgress ? 6 : 0 }}
                onClick={() => void onExportAllBoards()}
                disabled={exportingAll || !currentProject || boards.length === 0}
                title={exportingAll ? exportAllProgress : "Export all boards to Excel workbook"}
                aria-label="Export all boards to Excel workbook"
              >
                {exportingAll ? (
                  <RefreshCw className="h-2.5 w-2.5 shrink-0 animate-spin" />
                ) : (
                  <Download className="h-2.5 w-2.5 shrink-0" />
                )}
                {exportAllProgress && (
                  <span className="truncate text-[9px]" style={{ color: "var(--tt-text-muted)", maxWidth: "8rem" }}>
                    {exportAllProgress}
                  </span>
                )}
              </button>
              <button
                className="tt-btn-ghost shrink-0 !px-1.5 !py-0.5 !text-[10px] !gap-1"
                onClick={() => reloadBoards()}
                title="Refresh board list"
              >
                <RefreshCw className="h-2.5 w-2.5" />
                Refresh
              </button>
            </div>
          </div>
          <div className="min-h-0 flex-1 overflow-auto rounded-[8px] border border-[var(--tt-outline-soft)] bg-[var(--tt-surface-base)] p-1">
            {boards.length === 0 ? (
              <p className="px-2 py-2 text-xs text-muted-foreground">
                {currentProject ? "No boards found." : "Select a project first."}
              </p>
            ) : (
              boards.map((b) => {
                const isSelected = b.label === currentBoard?.label;
                const project = currentProject ? displayName(currentProject) : "";
                let boardLabel = (b.team_name || b.name || "").replace(/_/g, " ").trim();
                if (project && boardLabel.toLowerCase().startsWith(project.toLowerCase())) {
                  boardLabel = boardLabel.slice(project.length).replace(/^[\s\-–—:]+/, "").trim();
                }
                if (!boardLabel) boardLabel = b.team_name || b.label;
                return (
                  <div
                    key={b.id || b.label}
                    role="button"
                    tabIndex={0}
                    data-selected={isSelected}
                    onClick={() => selectBoard(b)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        selectBoard(b);
                      }
                    }}
                    className="tt-list-item flex items-center gap-2 text-sm"
                    title={b.label}
                  >
                    <span className="min-w-0 flex-1 truncate">{boardLabel}</span>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* ── Bottom toolbar ─────────────────────────────────────── */}
        <div className="grid grid-cols-2 gap-1 border-t border-[var(--tt-outline-soft)] pt-2 min-[300px]:grid-cols-3">
          <NavLabelBtn
            title="Check for updates"
            disabled={updateBusy}
            onClick={() => void onUpdateClick()}
            label={updateBusy ? "Checking..." : "Update"}
          />
          <Dropdown
            className="w-full"
            align="left"
            direction="up"
            items={[
              { label: "Open log folder", onClick: () => openLogFolder() },
              { label: "View recent log...", onClick: () => openDialog("viewlog") },
              { label: "About", separatorBefore: true, onClick: () => openDialog("about") },
            ]}
            trigger={({ toggle, ref }) => (
              <NavLabelBtn
                ref={ref}
                onClick={toggle}
                title="Help & About"
                label="Help"
              />
            )}
          />
          <NavLabelBtn
            title="Settings"
            onClick={() => openDialog("settings")}
            label="Settings"
          />
          <NavLabelBtn
            title="Project Knowledge Base"
            disabled={!currentProject}
            onClick={() => openDialog("kb")}
            label="Project KB"
          />
          <NavLabelBtn
            title="Manage encrypted test-environment credentials for E2E automation"
            disabled={!currentProject}
            onClick={() => openDialog("credentials")}
            label="Credentials"
          />
          <NavLabelBtn
            title={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
            aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
            onClick={toggleTheme}
            label="Theme"
          />
          <div className="col-span-full">
            <NavLabelBtn
              title="Collapse Navigation Bar"
              onClick={() => setNavVisible(false)}
              label="Collapse Navigation Bar"
            />
          </div>
        </div>
      </div>

      <ResizeHandle
        axis="x"
        value={width}
        min={180}
        max={480}
        onChange={setWidth}
        onCommit={(v) => setSizePref("navWidth", v)}
        ariaLabel="Resize navigator"
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Small reusable labeled icon button for the bottom toolbar
// ---------------------------------------------------------------------------
import React from "react";

/**
 * Text-only button for the EXPANDED nav bottom toolbar. Icons are intentionally
 * omitted here — the collapsed rail (ActivityBar) shows the icons instead, so
 * expanded mode stays text-only per product design.
 */
const NavLabelBtn = React.forwardRef<
  HTMLButtonElement,
  {
    title: string;
    onClick: () => void;
    label: string;
    disabled?: boolean;
    "aria-label"?: string;
  }
>(function NavLabelBtn({ title, onClick, label, disabled, ...rest }, ref) {
  return (
    <button
      ref={ref}
      title={title}
      aria-label={rest["aria-label"] ?? title}
      disabled={disabled}
      className="tt-btn-ghost flex h-9 w-full min-w-0 items-center justify-center !px-2 !text-[11px] disabled:opacity-40"
      onClick={onClick}
    >
      <span className="truncate">{label}</span>
    </button>
  );
});
