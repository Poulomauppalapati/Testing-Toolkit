"use client";

import {
  Folder,
  LayoutGrid,
  HelpCircle,
  Settings,
  Brain,
  ChevronRight,
  RefreshCw,
  KeyRound,
  Sun,
  Moon,
  type LucideIcon,
} from "lucide-react";
import { useAppState, type KbState } from "@/lib/app-state";
import { useTheme } from "@/lib/theme";
import { Dropdown } from "@/components/ui/dropdown";
import { agent } from "@/lib/agent-client";
import { useAppUpdate } from "@/lib/use-app-update";

const KB_BADGE: Record<KbState, string | undefined> = {
  none: "var(--tt-danger)",
  indexing: "var(--tt-warn)",
  context: "var(--tt-info)",
  ready: "var(--tt-success)",
  error: "var(--tt-danger)",
};

function RailButton({
  icon: Icon,
  label,
  onClick,
  disabled,
  badge,
}: {
  icon: LucideIcon;
  label: string;
  onClick?: () => void;
  disabled?: boolean;
  /** Optional badge color for the indicator dot. */
  badge?: string;
}) {
  return (
    <button
      onClick={onClick}
      title={label}
      aria-label={label}
      disabled={disabled}
      className="group relative h-8 w-8 shrink-0 rounded-lg border border-transparent p-0 text-[var(--tt-text-muted)] transition-all duration-150 hover:border-[var(--tt-primary)] hover:bg-[var(--tt-surface-container)] hover:text-[var(--tt-text-primary)] hover:shadow-[0_0_0_2px_rgba(111,154,201,0.16)] disabled:pointer-events-none disabled:opacity-40 flex items-center justify-center"
    >
      <Icon className="h-[18px] w-[18px]" strokeWidth={2} />
      {badge && (
        <span
          className="absolute right-1 top-1 h-2 w-2 rounded-full border border-[var(--tt-surface-deepest)]"
          style={{ background: badge }}
          aria-hidden
        />
      )}
    </button>
  );
}

export function ActivityBar() {
  const {
    setNavVisible,
    openDialog,
    currentProject,
    pushLog,
    setLogVisible,
    kbState,
  } = useAppState();

  const { theme, toggleTheme } = useTheme();
  const { check: checkForUpdate, busy: updateBusy } = useAppUpdate(pushLog);

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
    <div className="tt-rail flex w-11 shrink-0 flex-col items-center gap-1 py-2">
      {/* Update app — topmost, refresh logo only */}
      <button
        onClick={onUpdateClick}
        title="Check for updates"
        aria-label="Check for updates"
        disabled={updateBusy}
        className="group relative h-8 w-8 shrink-0 rounded-lg border border-transparent p-0 text-[var(--tt-text-muted)] transition-all duration-150 hover:border-[var(--tt-primary)] hover:bg-[var(--tt-surface-container)] hover:text-[var(--tt-text-primary)] hover:shadow-[0_0_0_2px_rgba(111,154,201,0.16)] disabled:pointer-events-none disabled:opacity-40 flex items-center justify-center"
      >
        <RefreshCw
          className={`h-[18px] w-[18px] ${updateBusy ? "animate-spin" : ""}`}
          strokeWidth={2}
        />
      </button>

      <RailButton icon={Folder} label="Projects" onClick={() => setNavVisible(true)} />
      <RailButton icon={LayoutGrid} label="Boards" onClick={() => setNavVisible(true)} />

      <div className="flex-1" />

      <Dropdown
        align="left"
        direction="up"
        items={[
          { label: "Open log folder", onClick: () => openLogFolder() },
          { label: "View recent log...", onClick: () => openDialog("viewlog") },
          { label: "About", separatorBefore: true, onClick: () => openDialog("about") },
        ]}
        trigger={({ toggle, ref }) => (
          <button
            ref={ref}
            onClick={toggle}
            title="Help"
            aria-label="Help"
            className="tt-btn-ghost h-8 w-8 shrink-0 !rounded-lg !border-transparent !p-0"
          >
            <HelpCircle className="h-[18px] w-[18px]" strokeWidth={2} />
          </button>
        )}
      />
      <RailButton icon={Settings} label="Settings" onClick={() => openDialog("settings")} />
      <RailButton
        icon={Brain}
        label="Project KB"
        onClick={() => openDialog("kb")}
        disabled={!currentProject}
        badge={currentProject ? KB_BADGE[kbState] : undefined}
      />
      <RailButton
        icon={KeyRound}
        label="Test credentials"
        onClick={() => openDialog("credentials")}
        disabled={!currentProject}
      />
      <RailButton
        icon={theme === "dark" ? Sun : Moon}
        label={theme === "dark" ? "Light theme" : "Dark theme"}
        onClick={toggleTheme}
      />
      <RailButton
        icon={ChevronRight}
        label="Show navigator"
        onClick={() => setNavVisible(true)}
      />
    </div>
  );
}
