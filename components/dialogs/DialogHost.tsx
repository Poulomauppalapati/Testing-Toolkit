"use client";

import type { ReactNode } from "react";
import { useAppState } from "@/lib/app-state";
import { SettingsDialog } from "./SettingsDialog";
import { GenerateDialog } from "./GenerateDialog";
import { ProjectKbDialog } from "./ProjectKbDialog";
import { UploadDialog } from "./UploadDialog";
import { PackageDialog } from "./PackageDialog";
import { DefectDialog } from "./DefectDialog";
import { RetrievalDialog } from "./RetrievalDialog";
import { ChatDialog } from "./ChatDialog";
import { CredentialsDialog } from "./CredentialsDialog";
import { E2EDialog } from "./E2EDialog";
import { AboutDialog } from "./AboutDialog";
import { ViewLogDialog } from "./ViewLogDialog";
import { AiStackDialog } from "./AiStackDialog";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { Modal } from "@/components/ui/modal";

function renderDialog(dialog: string, closeDialog: () => void): ReactNode {
  switch (dialog) {
    case "settings":
      return <SettingsDialog onClose={closeDialog} />;
    case "generate":
      return <GenerateDialog onClose={closeDialog} />;
    case "kb":
      return <ProjectKbDialog onClose={closeDialog} />;
    case "upload":
      return <UploadDialog onClose={closeDialog} />;
    case "package":
      return <PackageDialog onClose={closeDialog} />;
    case "defect":
      return <DefectDialog onClose={closeDialog} />;
    case "retrieval":
      return <RetrievalDialog onClose={closeDialog} />;
    case "chat":
      return <ChatDialog onClose={closeDialog} />;
    case "credentials":
      return <CredentialsDialog onClose={closeDialog} />;
    case "e2e":
      return <E2EDialog onClose={closeDialog} />;
    case "about":
      return <AboutDialog onClose={closeDialog} />;
    case "viewlog":
      return <ViewLogDialog onClose={closeDialog} />;
    case "aistack":
      return <AiStackDialog onClose={closeDialog} />;
    default:
      return null;
  }
}

export function DialogHost() {
  const { dialog, closeDialog } = useAppState();

  if (!dialog) return null;

  // Isolate each dialog: a render fault surfaces a recoverable error dialog
  // instead of white-screening the whole app (the board stays alive).
  return (
    <ErrorBoundary
      label="this dialog"
      resetKey={dialog}
      fallback={(error) => (
        <Modal open title="Something went wrong" onClose={closeDialog} width={480}>
          <div className="p-5 text-sm text-[var(--tt-text-muted)]">
            <p className="mb-2 text-[var(--tt-text-bright)]">
              This action hit an unexpected error and was stopped safely.
            </p>
            <p className="break-words text-xs text-[var(--tt-text-faint)]">
              {error.message || "Unknown error."}
            </p>
          </div>
        </Modal>
      )}
    >
      {renderDialog(dialog, closeDialog)}
    </ErrorBoundary>
  );
}
