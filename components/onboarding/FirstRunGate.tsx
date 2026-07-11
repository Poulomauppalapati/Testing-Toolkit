"use client";

import type { ReactNode } from "react";
import { agent } from "@/lib/agent-client";
import { useAppState } from "@/lib/app-state";
import { usePreferences } from "@/lib/preferences";
import { GuidedTour } from "@/components/onboarding/GuidedTour";

/**
 * Shows the optional guided tour once after the installed agent connects.
 * Work-item sources are configured later in Settings; having no ADO or JIRA
 * connection never blocks entry to the application shell.
 */
export function FirstRunGate({ children }: { children: ReactNode }) {
  const { settings, setSettings } = useAppState();
  const { prefs, setTourCompleted } = usePreferences();
  const tourCompleted = settings?.tour_completed === true || prefs.tourCompleted;

  const completeTour = () => {
    setTourCompleted(true);
    setSettings(settings ? { ...settings, tour_completed: true } : settings);
    agent.setTourCompleted(true).catch(() => {
      // Older agents may not persist tour state; the browser preference still
      // prevents the tour from blocking this session.
    });
  };

  return (
    <>
      {children}
      {!tourCompleted && <GuidedTour onDone={completeTour} />}
    </>
  );
}
