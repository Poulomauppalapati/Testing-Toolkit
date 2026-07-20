"""defects/uploader.py - Source-agnostic defect upload interface.

Routes defect creation to the appropriate source backend (ADO or JIRA)
through a unified API. Callers never import source-specific modules directly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from core.runtime_config import RuntimeConfig

LogFn = Callable[[str], None]
ProgressFn = Callable[[str, int, int], None]


@dataclass(slots=True)
class DefectCreateResult:
    title: str
    parent_id: str | int = 0
    created_id: str = ""
    created_url: str = ""
    ok: bool = True
    error: str = ""


@dataclass(slots=True)
class BulkDefectResult:
    results: list[DefectCreateResult] = field(default_factory=list)
    n_ok: int = 0
    n_failed: int = 0


async def upload_defects(
    defects: list[Any],
    source: str,
    org: str,
    project: str,
    pat: str,
    cfg: RuntimeConfig,
    on_log: LogFn | None = None,
    on_progress: ProgressFn | None = None,
    *,
    jira_url: str = "",
    jira_user: str = "",
) -> BulkDefectResult:
    """Upload parsed defects to the configured source.

    Args:
        source: "ado" or "jira"
        org: ADO organization (ignored for JIRA)
        project: project name/key
        pat: personal access token
        cfg: runtime config (SSL/proxy settings)
        jira_url: JIRA base URL (required when source="jira")
        jira_user: JIRA username/email (required when source="jira")
    """
    log = on_log or (lambda _: None)

    if source == "ado":
        from defects.ado_uploader import upload_defects_async
        return await upload_defects_async(
            defects, org, project, pat, cfg,
            on_log=log, on_progress=on_progress,
        )
    elif source == "jira":
        from defects.jira_uploader import upload_defects_jira
        return await upload_defects_jira(
            defects, jira_url, jira_user, pat, project, cfg,
            on_log=log, on_progress=on_progress,
        )
    else:
        raise ValueError(f"Unsupported defect source: {source!r}")
