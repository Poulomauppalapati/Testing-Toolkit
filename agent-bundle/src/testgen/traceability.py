"""Requirements Traceability Matrix builder.

Maps work items to their generated test cases and computes coverage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TraceabilityItem:
    """Single work item -> test cases mapping."""

    work_item_id: int
    work_item_title: str
    test_case_ids: list[str] = field(default_factory=list)

    @property
    def coverage_status(self) -> str:
        return "covered" if self.test_case_ids else "uncovered"


@dataclass
class TraceabilityMatrix:
    """Full traceability matrix with summary stats."""

    items: list[TraceabilityItem] = field(default_factory=list)

    @property
    def summary(self) -> dict[str, Any]:
        total: int = len(self.items)
        covered: int = sum(1 for i in self.items if i.coverage_status == "covered")
        return {
            "total_work_items": total,
            "covered": covered,
            "uncovered": total - covered,
            "coverage_pct": round((covered / total) * 100, 1) if total else 0.0,
        }

    def to_rows(self) -> list[dict[str, Any]]:
        """Flat row dicts for Excel export."""
        return [
            {
                "work_item_id": item.work_item_id,
                "work_item_title": item.work_item_title,
                "test_case_ids": ", ".join(item.test_case_ids),
                "test_case_count": len(item.test_case_ids),
                "coverage_status": item.coverage_status,
            }
            for item in self.items
        ]


def build_traceability(payload: dict[str, Any]) -> TraceabilityMatrix:
    """Build traceability matrix from test generation payload.

    Args:
        payload: Generated output with "stories" key containing work items
                 and their test cases.

    Returns:
        TraceabilityMatrix with coverage data for each work item.
    """
    items: list[TraceabilityItem] = []
    for story in payload.get("stories", []):
        tc_ids: list[str] = [
            tc["id"] for tc in story.get("test_cases", []) if "id" in tc
        ]
        items.append(
            TraceabilityItem(
                work_item_id=story.get("work_item_id", ""),
                work_item_title=story.get("title", ""),
                test_case_ids=tc_ids,
            )
        )
    return TraceabilityMatrix(items=items)
