"""KB endpoints — indexing, retrieval, embedding, reranking."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.app_config import PROJECTS_DIR
from agent.jobs import Job

router = APIRouter()


class RetrieveRequest(BaseModel):
    project: str
    query: str
    top_k: int = 32


class RetrieveResponse(BaseModel):
    chunks: list[dict[str, Any]]


@router.post("/retrieve", response_model=RetrieveResponse)
async def retrieve(req: RetrieveRequest) -> RetrieveResponse:
    """Run hybrid BM25 + dense + reranker search on the project KB."""
    from kb.retrieval import HybridRetriever

    project_dir = PROJECTS_DIR / req.project
    if not project_dir.exists():
        raise HTTPException(404, f"Project '{req.project}' not found locally")

    retriever = HybridRetriever(project_dir)
    if not retriever.is_ready():
        raise HTTPException(
            409, "KB index not built yet. Upload documents and trigger indexing first."
        )

    results = await asyncio.to_thread(retriever.retrieve, req.query, req.top_k)
    return RetrieveResponse(
        chunks=[
            {
                "chunk_id": r.chunk_id,
                "doc": r.doc,
                "title": r.title,
                "text": r.text,
                "score": r.score,
            }
            for r in results
        ]
    )


class EmbedRequest(BaseModel):
    texts: list[str]


@router.post("/embed")
async def embed(req: EmbedRequest) -> dict:
    """Embed texts using the local ONNX model."""
    from agent.model_loader import get_cached_embedder

    embedder = get_cached_embedder()
    if embedder is None:
        raise HTTPException(503, "Embedding model not available")

    vectors = await asyncio.to_thread(embedder.embed, req.texts)
    return {"vectors": [v.tolist() for v in vectors]}


class RerankRequest(BaseModel):
    query: str
    candidates: list[str]
    top_k: int = 32


@router.post("/rerank")
async def rerank(req: RerankRequest) -> dict:
    """Rerank candidates using the local cross-encoder model."""
    from agent.model_loader import get_cached_reranker

    reranker = get_cached_reranker()
    if reranker is None:
        raise HTTPException(503, "Reranker model not available")

    ranked = await asyncio.to_thread(
        reranker.rerank, req.query, req.candidates, req.top_k
    )
    return {"ranked": ranked}


class IndexRequest(BaseModel):
    project: str


def _run_kb_index(job: "Job", project: str) -> None:
    """Worker body mirroring MainWindow._kick_kb_index in the desktop app:
    build/refresh the resumable KB index while streaming per-file progress and
    log lines into the Job so the browser can render the same
    'KB indexing 3/10 | 12s / 30s - 30%' status the desktop footer shows."""
    import time as _time
    import core.project_store as ps

    start = _time.monotonic()

    def _fmt_duration(secs: float) -> str:
        s = int(max(0.0, secs))
        if s < 60:
            return f"{s}s"
        m, s = divmod(s, 60)
        return f"{m}m {s:02d}s"

    def _on_progress(done: int, total: int, _elapsed: float, name: str = "") -> None:
        # Carry the current filename in the stage slot for per-file display.
        job.set_progress(name or "indexing", int(done), int(total))
        if total > 0 and 0 < done < total:
            elapsed = _time.monotonic() - start
            pct = int(round(100.0 * done / max(total, 1)))
            if done > 0:
                remaining = elapsed / done * (total - done)
                timing = f"{_fmt_duration(elapsed)} / {_fmt_duration(remaining)} - {pct}%"
            else:
                timing = f"{_fmt_duration(elapsed)} / -- - {pct}%"
            label = f" ({name})" if name else ""
            job.log(f"[INFO] KB indexing {done}/{total}{label} | {timing}")

    def _on_log(msg: str) -> None:
        if msg:
            job.log(msg)

    def _should_stop() -> bool:
        return job.stopped

    # Build an LLM client for contextual retrieval (situating prefixes), using
    # the fast model for cost efficiency. Degrades gracefully if unavailable.
    ctx_client = None
    ctx_model = ""
    try:
        from core.settings_store import build_anthropic_client, model_pair
        ctx_client = build_anthropic_client()
        _, ctx_model = model_pair()
    except Exception:
        ctx_client = None
        ctx_model = ""

    try:
        job.log(f"[INFO] KB indexing started for '{project}'.")
        result = ps.index_project_resumable(
            project,
            on_progress=_on_progress,
            on_log=_on_log,
            should_stop=_should_stop,
            enable_dense=True,
            llm_client=ctx_client,
            llm_model=ctx_model,
        )
        docs = int(getattr(result, "n_docs", 0) or 0)
        chunks = len(getattr(result, "chunks", []) or [])
        job.finish({
            "n_documents": docs,
            "n_chunks": chunks,
            "has_dense": bool(getattr(result, "has_dense", False)),
        })
        if chunks > 0:
            job.log(
                f"[SUCCESS] KB indexing finished: {docs} doc(s), "
                f"{chunks} chunk(s); ready for generation."
            )
        else:
            job.log("[INFO] KB indexing finished: no indexable content.")
    except Exception as e:  # noqa: BLE001
        job.fail(f"{type(e).__name__}: {e}")
        job.log(f"[ERROR] KB indexing did not finish: {job.error}")


@router.post("/index")
async def index_project(req: IndexRequest) -> dict:
    """Start a background KB indexing run and return its job id. Poll
    /jobs/{job_id} for live per-file progress and logs, exactly like the
    desktop worker + footer. Mirrors MainWindow._kick_kb_index."""
    from agent.jobs import JOBS, Job

    project_dir = PROJECTS_DIR / req.project
    kb_dir = project_dir / "kb"
    if not kb_dir.exists():
        raise HTTPException(404, f"No kb/ folder found for project '{req.project}'")

    job = JOBS.create("kb_index")
    job.log("[INFO] Starting KB indexing...")
    asyncio.create_task(asyncio.to_thread(_run_kb_index, job, req.project))
    return {"job_id": job.id}


@router.post("/upload/{project}")
async def upload_document(
    project: str,
    file: UploadFile = File(...),
) -> dict:
    """Upload a document to the project's kb/ folder."""
    project_dir = PROJECTS_DIR / project
    kb_dir = project_dir / "kb"
    kb_dir.mkdir(parents=True, exist_ok=True)

    dest = kb_dir / file.filename
    content = await file.read()
    dest.write_bytes(content)
    return {"ok": True, "path": str(dest), "size": len(content)}


@router.get("/status/{project}")
async def kb_status(project: str) -> dict:
    """Return KB index status for a project."""
    project_dir = PROJECTS_DIR / project
    kb_dir = project_dir / "kb"
    index_file = project_dir / "kb_index.json"

    docs: list[str] = []
    if kb_dir.exists():
        docs = [f.name for f in kb_dir.iterdir() if f.is_file()]

    return {
        "project": project,
        "documents": docs,
        "indexed": index_file.exists(),
    }
