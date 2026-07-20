"""defects/jira_uploader.py - Create Bug issues in JIRA from reviewed defects.

Maps ParsedDefect fields to JIRA issue creation API. Parallel to ado_uploader
but targets JIRA REST API v2.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

import httpx

from core.runtime_config import RuntimeConfig
from defects.uploader import BulkDefectResult, DefectCreateResult

_log = logging.getLogger(__name__)

LogFn = Callable[[str], None]
ProgressFn = Callable[[str, int, int], None]

_CONCURRENCY = 4

_SEVERITY_TO_PRIORITY: dict[str, str] = {
    "1 - critical": "Highest",
    "2 - high": "High",
    "3 - medium": "Medium",
    "4 - low": "Low",
}


def _map_severity(severity: str) -> str:
    """Map defect severity (ADO-style 1-4) to JIRA priority name."""
    return _SEVERITY_TO_PRIORITY.get(severity.lower().strip(), "Medium")


def _build_description(defect: Any) -> str:
    """Build JIRA wiki-markup description from defect fields."""
    parts: list[str] = []
    if defect.description:
        parts.append(f"h3. Description\n{defect.description}")
    if defect.repro_steps:
        parts.append(f"h3. Repro Steps\n{defect.repro_steps}")
    if defect.expected_result:
        parts.append(f"h3. Expected Result\n{defect.expected_result}")
    if defect.actual_result:
        parts.append(f"h3. Actual Result\n{defect.actual_result}")
    return "\n\n".join(parts) or "No description provided."


async def _create_one(
    client: httpx.AsyncClient,
    project_key: str,
    defect: Any,
    semaphore: asyncio.Semaphore,
) -> DefectCreateResult:
    """Create a single Bug issue in JIRA."""
    result = DefectCreateResult(title=defect.title, parent_id=defect.parent_id)
    async with semaphore:
        try:
            payload = {
                "fields": {
                    "project": {"key": project_key},
                    "issuetype": {"name": "Bug"},
                    "summary": defect.title,
                    "description": _build_description(defect),
                    "priority": {"name": _map_severity(defect.severity)},
                }
            }
            resp = await client.post("/rest/api/2/issue", json=payload)
            if resp.status_code in (200, 201):
                data = resp.json()
                result.created_id = data.get("key", "")
                result.created_url = data.get("self", "")
                result.ok = True
            else:
                result.ok = False
                result.error = f"HTTP {resp.status_code}: {resp.text[:200]}"
        except Exception as exc:
            result.ok = False
            result.error = f"{type(exc).__name__}: {exc}"
    return result


async def upload_defects_jira(
    defects: list[Any],
    url: str,
    user: str,
    pat: str,
    project_key: str,
    cfg: RuntimeConfig,
    on_log: LogFn | None = None,
    on_progress: ProgressFn | None = None,
) -> BulkDefectResult:
    """Upload parsed defects to JIRA as Bug issues."""
    log = on_log or (lambda _: None)
    progress = on_progress or (lambda *_: None)
    total = len(defects)
    log(f"[INFO] Uploading {total} defect(s) to JIRA project {project_key}...")

    import base64
    token = base64.b64encode(f"{user}:{pat}".encode("ascii")).decode("ascii")
    headers = {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    verify = cfg.ssl_verify if hasattr(cfg, "ssl_verify") else True
    semaphore = asyncio.Semaphore(_CONCURRENCY)

    async with httpx.AsyncClient(
        base_url=url.rstrip("/"),
        headers=headers,
        verify=verify,
        timeout=30.0,
    ) as client:
        tasks = [
            _create_one(client, project_key, d, semaphore)
            for d in defects
        ]
        results: list[DefectCreateResult] = []
        for i, coro in enumerate(asyncio.as_completed(tasks), 1):
            r = await coro
            results.append(r)
            progress("upload", i, total)
            if r.ok:
                log(f"[SUCCESS] Created {r.created_id}: {r.title}")
            else:
                log(f"[ERROR] Failed: {r.title} - {r.error}")

    n_ok = sum(1 for r in results if r.ok)
    return BulkDefectResult(results=results, n_ok=n_ok, n_failed=total - n_ok)
