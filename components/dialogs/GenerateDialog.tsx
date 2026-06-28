"use client";

import { useState } from "react";
import { Modal } from "@/components/ui/modal";
import {
  agent,
  agentLogLevel,
  TC_DISPLAY_NAME,
  type GenerationResult,
  type JobProgress,
  type TcType,
} from "@/lib/agent-client";
import { useAppState } from "@/lib/app-state";

const MAX_ITERATIONS = 10;

export function GenerateDialog({ onClose }: { onClose: () => void }) {
  const {
    selected,
    boardView,
    currentProject,
    displayName,
    generateCtx,
    settings,
    pushLog,
  } = useAppState();
  const [mode, setMode] = useState<"auto" | "manual">(
    settings?.has_api_key ? "auto" : "manual"
  );
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [iteration, setIteration] = useState(0);
  const [result, setResult] = useState<GenerationResult | null>(null);
  const [manualJson, setManualJson] = useState("");
  const [status, setStatus] = useState("");
  const [progress, setProgress] = useState<JobProgress | null>(null);
  const [pushed, setPushed] = useState<string>("");

  const tcType = generateCtx.tcType as TcType | "";
  const phase = tcType ? TC_DISPLAY_NAME[tcType] : "test case";
  const ids = [...selected].sort((a, b) => a - b);
  const rows = (boardView?.rows ?? []).filter((r) => selected.has(r.wi_id));

  const handlers = {
    onLog: (line: string) => pushLog(agentLogLevel(line), line),
    onProgress: (p: JobProgress) => setProgress(p),
  };

  const run = async (isRegen: boolean) => {
    if (!currentProject) return;
    setBusy(true);
    setPushed("");
    setProgress(null);
    setStatus(
      isRegen ? "Regenerating with feedback..." : "Generating test cases..."
    );
    pushLog(
      "INFO",
      `Generating ${phase} test cases for ${ids.length} work item(s)...`
    );
    try {
      const res = await agent.generate(
        {
          project: currentProject,
          wi_ids: ids,
          tc_type: tcType,
          regen_feedback: isRegen ? feedback : "",
          base_payload: isRegen ? result?.payload ?? null : null,
        },
        handlers
      );
      setResult(res);
      if (isRegen) setIteration((i) => i + 1);
      setFeedback("");
      setStatus(`Generated ${res.n_test_cases} test case(s). Review, then push.`);
      pushLog("SUCCESS", `Generated ${res.n_test_cases} test case(s).`);
    } catch (e) {
      setStatus(`Generation failed: ${(e as Error).message}`);
      pushLog("ERROR", `Generation failed: ${(e as Error).message}`);
    } finally {
      setBusy(false);
      setProgress(null);
    }
  };

  const runManual = async (payload: Record<string, unknown>) => {
    if (!currentProject) return;
    setBusy(true);
    setPushed("");
    setStatus("Validating pasted JSON...");
    try {
      const res = await agent.generate(
        {
          project: currentProject,
          wi_ids: ids,
          tc_type: tcType,
          manual_payload: payload,
        },
        handlers
      );
      setResult(res);
      setStatus(`Loaded ${res.n_test_cases} test case(s). Review, then push.`);
      pushLog("SUCCESS", `Manual payload accepted: ${res.n_test_cases} TC(s).`);
    } catch (e) {
      setStatus(`Validation failed: ${(e as Error).message}`);
      pushLog("ERROR", `Manual payload failed: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  const push = async () => {
    if (!currentProject || !result) return;
    setBusy(true);
    setStatus("Creating test cases in Azure DevOps...");
    try {
      const res = await agent.pushPayload(
        { project: currentProject, payload: result.payload },
        handlers
      );
      setPushed(`Created ${res.n_ok} test case(s), ${res.n_failed} failed.`);
      setStatus(`Created ${res.n_ok} test case(s) in ADO.`);
      pushLog("SUCCESS", `Created ${res.n_ok} test case(s) in ADO.`);
    } catch (e) {
      setStatus(`Push failed: ${(e as Error).message}`);
      pushLog("ERROR", `Push failed: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  const progressPct =
    progress && progress.total > 0
      ? Math.round((progress.current / progress.total) * 100)
      : null;

  return (
    <Modal
      open
      onClose={onClose}
      title={`Generate ${phase} Test Cases`}
      subtitle={
        currentProject
          ? `${displayName(currentProject)} · ${ids.length} work item(s) selected`
          : undefined
      }
      width={760}
      footer={
        <>
          {status && (
            <span className="mr-auto text-xs text-muted-foreground">
              {status}
              {progressPct != null && ` · ${progress?.stage} ${progressPct}%`}
            </span>
          )}
          <button className="tt-btn-ghost" onClick={onClose} disabled={busy}>
            Close
          </button>
          {mode === "auto" && !result && (
            <button
              className="tt-btn-success"
              onClick={() => run(false)}
              disabled={busy || !ids.length}
            >
              {busy ? "Generating..." : "Generate"}
            </button>
          )}
          {result && (
            <button
              className="tt-btn-success"
              onClick={push}
              disabled={busy}
              title="Create the reviewed test cases in Azure DevOps"
            >
              {busy ? "Working..." : "Push to ADO"}
            </button>
          )}
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {/* Mode toggle */}
        <div className="flex items-center gap-2">
          <button
            className="tt-btn-ghost !px-3 !py-1 text-xs"
            data-active={mode === "auto"}
            onClick={() => setMode("auto")}
          >
            Automatic (API)
          </button>
          <button
            className="tt-btn-ghost !px-3 !py-1 text-xs"
            data-active={mode === "manual"}
            onClick={() => setMode("manual")}
          >
            Manual Mode
          </button>
          {!settings?.has_api_key && (
            <span className="text-xs text-[#f59e0b]">
              No API key configured — Manual Mode recommended.
            </span>
          )}
        </div>

        {/* Selected work items */}
        <div className="flex flex-col gap-1.5">
          <h4 className="text-xs font-bold uppercase tracking-wide text-[#7abaff]">
            Selected work items
          </h4>
          <div className="max-h-32 overflow-auto rounded-lg border border-[#2d313c] bg-[#13161d] p-2">
            {rows.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No work items selected.
              </p>
            ) : (
              rows.map((r) => (
                <div key={r.wi_id} className="truncate py-0.5 text-sm">
                  <span className="font-semibold text-[#5ba8ff]">
                    #{r.wi_id}
                  </span>{" "}
                  <span className="text-[#bfc4cc]">{r.title}</span>
                </div>
              ))
            )}
          </div>
        </div>

        {mode === "auto" ? (
          <div className="flex flex-col gap-3">
            <div className="tt-help p-3 text-xs leading-relaxed">
              <div className="tt-help-header mb-1">
                Recursive Language Model pipeline
              </div>
              <div className="tt-help-body">
                Navigate → Map → Decompose → Generate (extended thinking) → Verify
                + Gap-Fill. Coverage verification and gap-fill are always on. KBs
                up to ~375 pages are passed whole for full coverage.
              </div>
            </div>

            {result && (
              <ReviewCard
                result={result}
                pushed={pushed}
                feedback={feedback}
                setFeedback={setFeedback}
                iteration={iteration}
                busy={busy}
                onRegenerate={() => run(true)}
              />
            )}
          </div>
        ) : (
          <ManualMode
            project={currentProject}
            ids={ids}
            tcType={tcType}
            manualJson={manualJson}
            setManualJson={setManualJson}
            busy={busy}
            onValidate={runManual}
            pushLog={pushLog}
          />
        )}
      </div>
    </Modal>
  );
}

function ReviewCard({
  result,
  pushed,
  feedback,
  setFeedback,
  iteration,
  busy,
  onRegenerate,
}: {
  result: GenerationResult;
  pushed: string;
  feedback: string;
  setFeedback: (v: string) => void;
  iteration: number;
  busy: boolean;
  onRegenerate: () => void;
}) {
  return (
    <div className="flex flex-col gap-2 rounded-lg border border-[#1aab5c]/40 bg-[#0d2a1c] p-3">
      <p className="text-sm text-[#22c46a]">
        {result.n_test_cases} test case(s) across {result.n_stories} story(ies).
      </p>
      <a
        className="break-all text-xs text-[#5ba8ff] hover:underline"
        href={agent.artifactDownloadUrl(result.xlsx_path)}
        target="_blank"
        rel="noopener noreferrer"
      >
        Download review Excel: {result.xlsx_name}
      </a>
      {pushed && <p className="text-sm text-[#22c46a]">{pushed}</p>}
      <div className="mt-1 flex flex-col gap-1.5">
        <label className="text-xs text-[#bfc4cc]">
          Regeneration feedback (iteration {iteration}/{MAX_ITERATIONS})
        </label>
        <textarea
          className="tt-input min-h-20 resize-y"
          placeholder="Describe changes to apply, then Regenerate..."
          value={feedback}
          onChange={(e) => setFeedback(e.target.value)}
          disabled={iteration >= MAX_ITERATIONS || busy}
        />
        <div className="flex justify-end">
          <button
            className="tt-btn-success !px-4 !py-1.5 text-sm"
            onClick={onRegenerate}
            disabled={busy || !feedback.trim() || iteration >= MAX_ITERATIONS}
          >
            Regenerate
          </button>
        </div>
      </div>
    </div>
  );
}

function ManualMode({
  project,
  ids,
  tcType,
  manualJson,
  setManualJson,
  busy,
  onValidate,
  pushLog,
}: {
  project: string;
  ids: number[];
  tcType: TcType | "";
  manualJson: string;
  setManualJson: (v: string) => void;
  busy: boolean;
  onValidate: (payload: Record<string, unknown>) => void;
  pushLog: (level: "INFO" | "SUCCESS" | "WARN" | "ERROR", t: string) => void;
}) {
  const [prompt, setPrompt] = useState("");
  const [dump, setDump] = useState("");
  const [loading, setLoading] = useState(false);
  const [jsonError, setJsonError] = useState("");

  const loadContext = async () => {
    if (!project) return;
    setLoading(true);
    try {
      const res = await agent.buildDump(project, ids, tcType);
      setPrompt(res.system_prompt || "");
      setDump(res.dump || "");
      pushLog("SUCCESS", `Loaded prompt + dump for ${res.n_items} item(s).`);
    } catch (e) {
      pushLog("WARN", `Could not load manual context: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  };

  const validate = () => {
    setJsonError("");
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(manualJson);
    } catch (e) {
      setJsonError(`Invalid JSON: ${(e as Error).message}`);
      return;
    }
    onValidate(parsed);
  };

  const copy = (text: string) => navigator.clipboard?.writeText(text);

  return (
    <div className="flex flex-col gap-3">
      <div className="tt-help p-3 text-xs leading-relaxed">
        <div className="tt-help-header mb-1">Manual Mode</div>
        <div className="tt-help-body">
          Copy the system prompt and work-item dump into any LLM session, then
          paste the returned JSON below and validate it. The review and push
          steps are identical to automatic mode.
        </div>
      </div>

      <button
        className="tt-btn-ghost self-start !px-3 !py-1.5 text-xs"
        onClick={loadContext}
        disabled={loading || !project}
      >
        {loading ? "Loading..." : "Load prompt & work-item dump"}
      </button>

      {prompt && (
        <CopyBlock
          label="System prompt"
          text={prompt}
          onCopy={() => copy(prompt)}
        />
      )}
      {dump && (
        <CopyBlock
          label="Work-item dump"
          text={dump}
          onCopy={() => copy(dump)}
        />
      )}

      <div className="flex flex-col gap-1.5">
        <label className="text-xs font-bold uppercase tracking-wide text-[#7abaff]">
          Paste JSON response
        </label>
        <textarea
          className="tt-input min-h-28 resize-y font-mono text-xs"
          placeholder='{"stories": [...]}'
          value={manualJson}
          onChange={(e) => setManualJson(e.target.value)}
        />
        {jsonError && <p className="text-xs text-[#ef4444]">{jsonError}</p>}
        <div className="flex justify-end">
          <button
            className="tt-btn-primary !px-4 !py-1.5 text-sm"
            onClick={validate}
            disabled={busy || !manualJson.trim()}
          >
            {busy ? "Validating..." : "Validate & Load"}
          </button>
        </div>
      </div>
    </div>
  );
}

function CopyBlock({
  label,
  text,
  onCopy,
}: {
  label: string;
  text: string;
  onCopy: () => void;
}) {
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between">
        <span className="text-xs font-bold uppercase tracking-wide text-[#7abaff]">
          {label}
        </span>
        <button className="tt-btn-ghost !px-2 !py-1 text-xs" onClick={onCopy}>
          Copy
        </button>
      </div>
      <pre className="max-h-40 overflow-auto rounded-lg border border-[#2d313c] bg-[#0d1017] p-2 font-mono text-xs text-[#bfc4cc]">
        {text}
      </pre>
    </div>
  );
}
