"""
protocols.py
Shared Protocol definitions for the Testing Toolkit. These define the
contracts between UI and backend implementations (ADO, JIRA) without
coupling them via concrete imports.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class TestCaseCreator(Protocol):
    """Contract for test case upload backends (ADO, JIRA)."""

    async def create_test_cases_async(
        self,
        payload: list[dict[str, Any]],
        *,
        on_progress: Any | None = None,
        on_log: Any | None = None,
    ) -> Any:
        ...


@runtime_checkable
class DefectUploader(Protocol):
    """Contract for defect upload backends (ADO, JIRA)."""

    async def upload_defects_async(
        self,
        defects: list[dict[str, Any]],
        *,
        on_progress: Any | None = None,
        on_log: Any | None = None,
    ) -> Any:
        ...


@runtime_checkable
class ProjectSource(Protocol):
    """Contract for project listing backends."""

    @property
    def source_id(self) -> str:
        """Unique identifier for this source ('ado' or 'jira')."""
        ...

    @property
    def display_name(self) -> str:
        """Human-readable source label ('Azure DevOps' or 'JIRA')."""
        ...

    async def list_projects(self) -> list[str]:
        ...

    async def verify_connection(self) -> tuple[bool, str]:
        ...


@runtime_checkable
class WorkItemTagger(Protocol):
    """Contract for tagging work items post-automation."""

    async def tag_work_item(
        self,
        item_id: str,
        tag: str,
        *,
        on_log: Any | None = None,
    ) -> bool:
        ...


