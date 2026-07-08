"use client";

import { useMemo, useState } from "react";
import { Modal } from "@/components/ui/modal";
import { agent, type RetrievedChunk } from "@/lib/agent-client";
import { useAppState } from "@/lib/app-state";

const DEFAULT_TOP_K = 32;
const SNIPPET_CHARS = 600;

/**
 * Retrieval preview — web port of the desktop RetrievalPreviewDialog.
 * Paste story text and see which KB chunks the local hybrid retriever would
 * feed the model, ranked and scored, with NO LLM call and NO ADO changes.
 */
export function RetrievalDialog({ onClose }: { onClose: () => void }) {
  const { currentProject, displayName } = useAppState();
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(DEFAULT_TOP_K);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const [chunks, setChunks] = useState<RetrievedChunk[] | null>(null);

  const preview = async () => {
    const text = query.trim();
    if (!text || !currentProject) {
      setNote("Paste some story text first.");
      return;
    }
    setBusy(true);
    setNote("Retrieving (local, no API)...");
    setChunks(null);
    try {
      const res = await agent.kbRetrieve(currentProject, text, topK);
      setChunks(res);
      setNote(`Retrieved ${res.length} chunk(s).`);
    } catch (e) {
      const msg = (e as Error).message;
      // 409 -> index not built yet.
      if (/index/i.test(msg)) {
        setNote(
          "No KB index for this project yet. Open Project KB, let indexing finish, then try again."
        );
      } else {
        setNote(`Retrieval failed: ${msg}`);
      }
    } finally {
      setBusy(false);
    }
  };

  const coverage = useMemo(() => {
    if (!chunks || chunks.length === 0) return "";
    const tally: Record<string, number> = {};
    for (const c of chunks) tally[c.doc] = (tally[c.doc] ?? 0) + 1;
    return Object.entries(tally)
      .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
      .map(([d, n]) => `${d} x${n}`)
      .join(", ");
  }, [chunks]);

  return (
    <Modal
      open
      onClose={onClose}
      title={`Retrieval preview${
        currentProject ? ` - ${displayName(currentProject)}` : ""
      }`}
      width={960}
      footer={
        <>
          {note && (
            <span className="mr-auto text-xs text-muted-foreground">{note}</span>
          )}
          <button className="tt-btn-ghost" onClick={onClose} disabled={busy}>
            Close
          </button>
          <button
            className="tt-btn-primary"
            onClick={preview}
            disabled={busy || !currentProject || !query.trim()}
          >
            {busy ? "Retrieving..." : "Preview retrieval"}
          </button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <div className="tt-help p-3 text-xs leading-relaxed">
          <div className="tt-help-header mb-1">What this shows</div>
          <div className="tt-help-body">
            Paste a user story (or any work-item text). This shows the KB chunks
            the local retriever would supply for it — ranked, scored, and by
            source — with no LLM API call and no ADO changes. Use it to
            sanity-check retrieval before generating.
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <h4 className="text-xs font-bold uppercase tracking-wide text-[var(--tt-primary-soft)]">
            Story / work-item text
          </h4>
          <textarea
            className="tt-input min-h-28 resize-y text-sm"
            placeholder="Paste the user story title and description here..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <div className="flex items-center gap-2">
            <label className="text-xs text-[var(--tt-text-secondary)]">
              Chunks to retrieve
            </label>
            <input
              className="tt-input w-20 !py-1 text-xs"
              type="number"
              min={1}
              max={50}
              value={topK}
              onChange={(e) =>
                setTopK(
                  Math.max(1, Math.min(50, parseInt(e.target.value, 10) || 1))
                )
              }
            />
            <span className="text-xs text-[var(--tt-text-muted)]">
              Generation uses 16 by default.
            </span>
          </div>
        </div>

        {chunks && chunks.length > 0 && (
          <div className="flex flex-col gap-2">
            <div className="text-xs text-[var(--tt-text-muted)]">
              Source coverage: {coverage}
            </div>
            <div className="max-h-[44vh] overflow-auto rounded-lg border border-[var(--tt-outline)] bg-[var(--tt-surface-base)] p-3 font-mono text-xs">
              {chunks.map((c, i) => {
                const snippet = c.text.replace(/\s+/g, " ").trim();
                const shown =
                  snippet.length > SNIPPET_CHARS
                    ? snippet.slice(0, SNIPPET_CHARS) + " ..."
                    : snippet;
                return (
                  <div
                    key={c.chunk_id || i}
                    className="mb-3 border-b border-[var(--tt-outline-soft)] pb-3 last:border-0"
                  >
                    <div className="text-[var(--tt-primary-soft)]">
                      {`#${i + 1}`} score={c.score.toFixed(4)} {c.doc}
                      {c.title ? ` - ${c.title}` : ""}
                    </div>
                    <div className="mt-1 text-[var(--tt-text-secondary)]">
                      {shown}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {chunks && chunks.length === 0 && (
          <div className="rounded-lg border border-[var(--tt-outline)] bg-[var(--tt-surface-base)] p-3 text-sm text-[var(--tt-text-secondary)]">
            No chunks matched. Try broader wording, or confirm the KB is indexed.
          </div>
        )}
      </div>
    </Modal>
  );
}
