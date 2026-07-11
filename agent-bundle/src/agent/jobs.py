"""Durable registry for long-running local-agent work."""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from core.app_config import WORKSPACE

_MAX_JOBS: Final[int] = 100
_TTL_SECONDS: Final[float] = 24 * 3600.0
_MAX_LOG_LINES: Final[int] = 200_000
_STATE_DIR: Final[Path] = WORKSPACE / "jobs"
_STATE_PATH: Final[Path] = _STATE_DIR / "registry.json"


@dataclass(slots=True)
class Job:
    id: str
    kind: str
    project: str = ""
    state: str = "running"
    logs: list[str] = field(default_factory=list)
    progress_stage: str = ""
    progress_current: int = 0
    progress_total: int = 0
    error: str = ""
    result: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    resumable: bool = False
    recovery: dict[str, Any] = field(default_factory=dict)
    interrupted: bool = False
    stop_event: threading.Event = field(default_factory=threading.Event, repr=False)
    _persist: Any = field(default=None, repr=False)

    def _changed(self) -> None:
        self.updated_at = time.time()
        if self._persist is not None:
            self._persist()

    def log(self, msg: str) -> None:
        if not msg:
            return
        self.logs.append(str(msg))
        if len(self.logs) > _MAX_LOG_LINES:
            del self.logs[: len(self.logs) - _MAX_LOG_LINES]
        self._changed()

    def set_progress(self, stage: str, current: int, total: int) -> None:
        self.progress_stage = str(stage)
        self.progress_current = max(0, int(current))
        self.progress_total = max(0, int(total))
        self._changed()

    def checkpoint(self, **values: Any) -> None:
        self.recovery.update(values)
        self._changed()

    def finish(self, result: dict[str, Any] | None = None) -> None:
        if result is not None:
            self.result = result
        self.state = "done"
        self.interrupted = False
        self._changed()

    def fail(self, error: str) -> None:
        self.error = str(error)
        self.state = "error"
        self._changed()

    def request_stop(self) -> None:
        self.stop_event.set()
        self._changed()

    @property
    def stopped(self) -> bool:
        return self.stop_event.is_set()

    def snapshot(self, log_offset: int = 0) -> dict[str, Any]:
        offset = max(0, int(log_offset))
        return {
            "id": self.id,
            "kind": self.kind,
            "project": self.project,
            "state": self.state,
            "logs": self.logs[offset:],
            "log_count": len(self.logs),
            "progress": {
                "stage": self.progress_stage,
                "current": self.progress_current,
                "total": self.progress_total,
            },
            "error": self.error,
            "result": self.result,
            "resumable": self.resumable,
            "interrupted": self.interrupted,
            "recovery": self.recovery,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def durable_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "project": self.project,
            "state": self.state,
            "logs": list(self.logs),
            "progress_stage": self.progress_stage,
            "progress_current": self.progress_current,
            "progress_total": self.progress_total,
            "error": self.error,
            "result": dict(self.result),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "resumable": self.resumable,
            "recovery": dict(self.recovery),
            "interrupted": self.interrupted,
        }


class JobManager:
    def __init__(self, state_path: Path = _STATE_PATH) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.RLock()
        self._state_path = state_path
        self._load()

    def _bind(self, job: Job) -> Job:
        job._persist = self._persist
        return job

    def _load(self) -> None:
        try:
            raw = json.loads(self._state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return
        for item in raw.get("jobs", []):
            if not isinstance(item, dict):
                continue
            try:
                job = Job(**{key: value for key, value in item.items() if key not in {"stop_event", "_persist"}})
            except (TypeError, ValueError):
                continue
            if job.state == "running":
                job.interrupted = True
                if job.resumable:
                    job.state = "recovering"
                    job.logs.append("[WARN] Agent restarted; queued for safe recovery.")
                else:
                    job.state = "error"
                    job.error = "Agent restarted during a non-resumable operation."
                    job.logs.append("[ERROR] Operation interrupted by agent restart.")
            self._jobs[job.id] = self._bind(job)
        self._gc()
        self._persist()

    def _persist(self) -> None:
        with self._lock:
            try:
                self._state_path.parent.mkdir(parents=True, exist_ok=True)
                temp = self._state_path.with_suffix(f".tmp-{os.getpid()}")
                payload = {
                    "schema": 1,
                    "updated_at": time.time(),
                    "jobs": [job.durable_dict() for job in self._jobs.values()],
                }
                temp.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
                os.replace(temp, self._state_path)
            except OSError:
                return

    def create(
        self,
        kind: str,
        project: str = "",
        *,
        resumable: bool = False,
        recovery: dict[str, Any] | None = None,
    ) -> Job:
        with self._lock:
            self._gc()
            job = self._bind(Job(
                id=uuid.uuid4().hex[:12],
                kind=kind,
                project=project,
                resumable=resumable,
                recovery=dict(recovery or {}),
            ))
            self._jobs[job.id] = job
            self._persist()
            return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def find_active(self, kind: str, project: str = "") -> Job | None:
        with self._lock:
            candidates = [
                job for job in self._jobs.values()
                if job.kind == kind
                and job.state in {"running", "recovering"}
                and (not project or job.project == project)
            ]
            return max(candidates, key=lambda job: job.created_at) if candidates else None

    def recovering(self, kind: str = "") -> list[Job]:
        with self._lock:
            return [
                job for job in self._jobs.values()
                if job.state == "recovering" and (not kind or job.kind == kind)
            ]

    def mark_running(self, job: Job) -> None:
        job.state = "running"
        job.interrupted = False
        job.error = ""
        job._changed()

    def _gc(self) -> None:
        now = time.time()
        for job_id in list(self._jobs):
            job = self._jobs[job_id]
            if job.state not in {"running", "recovering"} and now - job.updated_at > _TTL_SECONDS:
                self._jobs.pop(job_id, None)
        if len(self._jobs) > _MAX_JOBS:
            terminal = sorted(
                (job for job in self._jobs.values() if job.state not in {"running", "recovering"}),
                key=lambda job: job.updated_at,
            )
            for job in terminal:
                if len(self._jobs) <= _MAX_JOBS:
                    break
                self._jobs.pop(job.id, None)


JOBS: Final[JobManager] = JobManager()
