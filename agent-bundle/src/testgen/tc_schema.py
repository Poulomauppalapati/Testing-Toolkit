"""Shared test-case schema constants, normalization, and validation.

Source-agnostic: these define the universal test-case schema used by both
ADO and JIRA creation paths. Moved here from ado/testcase_creator.py to
break the testgen -> ado import cycle.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Final

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------
# Valid schema values
# ---------------------------------------------------------------------
VALID_CATEGORIES: Final[tuple[str, ...]] = (
    "Accessibility",
    "API Validation",
    "Browser",
    "Bug Validation",
    "Data Validation",
    "Error Handling",
    "GUI Validation",
    "Integration",
    "Mobile Platform",
    "N/A",
    "Negative",
    "Performance",
    "Positive",
    "Regression",
    "UAT",
)

VALID_PRIORITIES: Final[tuple[str, ...]] = ("Lowest", "Low", "Medium", "High")

_CATEGORY_ALIASES: Final[dict[str, str]] = {
    "boundary": "Data Validation",
    "boundary value": "Data Validation",
    "bva": "Data Validation",
    "validation": "Data Validation",
    "field validation": "Data Validation",
    "input validation": "Data Validation",
    "functional": "Positive",
    "happy path": "Positive",
    "smoke": "Positive",
    "sanity": "Positive",
    "end to end": "Integration",
    "e2e": "Integration",
    "workflow": "Integration",
    "security": "Negative",
    "authorization": "Negative",
    "authentication": "Negative",
    "permission": "Negative",
    "negative testing": "Negative",
    "error": "Error Handling",
    "exception": "Error Handling",
    "ui": "GUI Validation",
    "ux": "GUI Validation",
    "gui": "GUI Validation",
    "usability": "GUI Validation",
    "interface": "GUI Validation",
    "api": "API Validation",
    "integration testing": "Integration",
    "compatibility": "Browser",
    "cross browser": "Browser",
    "cross-browser": "Browser",
    "mobile": "Mobile Platform",
    "responsive": "Mobile Platform",
    "load": "Performance",
    "stress": "Performance",
    "a11y": "Accessibility",
    "wcag": "Accessibility",
    "regression testing": "Regression",
}

_CATEGORY_CANON: Final[dict[str, str]] = {c.lower(): c for c in VALID_CATEGORIES}


# ---------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------
def normalize_category(cat: Any) -> str:
    """Coerce a category string to a VALID category."""
    if not isinstance(cat, str):
        return "Positive"
    key = cat.strip().lower()
    if key in _CATEGORY_CANON:
        return _CATEGORY_CANON[key]
    if key in _CATEGORY_ALIASES:
        return _CATEGORY_ALIASES[key]
    return "Positive"


def normalize_priority(pr: Any) -> str | None:
    """Coerce a priority string to a valid value, or None."""
    if pr is None:
        return None
    if not isinstance(pr, str):
        return "Medium"
    key = pr.strip().lower()
    table = {"lowest": "Lowest", "low": "Low", "medium": "Medium",
             "high": "High", "critical": "High", "highest": "High",
             "1": "High", "2": "High", "3": "Medium", "4": "Low",
             "1 - critical": "High", "2 - high": "High",
             "3 - medium": "Medium", "4 - low": "Low"}
    return table.get(key, "Medium")


def normalize_payload(data: Any) -> Any:
    """Coerce every test case's category and priority to valid values."""
    try:
        stories = data.get("stories") if isinstance(data, dict) else None
        if not isinstance(stories, list):
            return data
        for story in stories:
            tcs = story.get("test_cases") if isinstance(story, dict) else None
            if not isinstance(tcs, list):
                continue
            for tc in tcs:
                if not isinstance(tc, dict):
                    continue
                tc["category"] = normalize_category(tc.get("category"))
                if "priority" in tc:
                    np = normalize_priority(tc.get("priority"))
                    if np is None:
                        tc.pop("priority", None)
                    else:
                        tc["priority"] = np
    except Exception as e:
        _log.debug("normalize_payload failed: %s", e)
    return data


# ---------------------------------------------------------------------
# Title cleaning
# ---------------------------------------------------------------------
_TITLE_PREFIX_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s*"
    r"(?:TC\s*[:\-]\s*)?"
    r"(?:(?:" + "|".join(
        re.escape(c) for c in VALID_CATEGORIES
    ) + r")\s*[-–—:]\s*)?"
    r"",
    re.IGNORECASE,
)


def clean_title(raw: str) -> str:
    """Strip 'TC:' and any '<Category> - ' prefix from a test case title."""
    if not raw:
        return ""
    m = _TITLE_PREFIX_RE.match(raw)
    cleaned = raw[m.end():].strip() if m else raw.strip()
    return cleaned or raw.strip()


# ---------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------
@dataclass(slots=True)
class ValidationReport:
    ok: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    n_stories: int = 0
    n_test_cases: int = 0


def validate_payload(data: Any) -> ValidationReport:
    """Validate the LLM JSON output against the strict schema."""
    r = ValidationReport()

    if not isinstance(data, dict):
        r.ok = False
        r.errors.append("Root must be a JSON object.")
        return r

    sv = data.get("schema_version")
    if sv != 1:
        r.warnings.append(
            f"Unexpected schema_version={sv!r}. Continuing, but the "
            f"payload may break if the schema has changed."
        )

    stories = data.get("stories")
    if not isinstance(stories, list) or not stories:
        r.ok = False
        r.errors.append("'stories' must be a non-empty list.")
        return r
    r.n_stories = len(stories)

    for si, story in enumerate(stories):
        prefix = f"stories[{si}]"
        if not isinstance(story, dict):
            r.errors.append(f"{prefix}: must be an object.")
            r.ok = False
            continue

        wid = story.get("parent_work_item_id")
        if not isinstance(wid, int) or wid <= 0:
            r.errors.append(
                f"{prefix}.parent_work_item_id must be a positive int."
            )
            r.ok = False

        tcs = story.get("test_cases")
        if not isinstance(tcs, list) or not tcs:
            r.errors.append(
                f"{prefix}.test_cases must be a non-empty list."
            )
            r.ok = False
            continue

        for ti, tc in enumerate(tcs):
            tcp = f"{prefix}.test_cases[{ti}]"
            if not isinstance(tc, dict):
                r.errors.append(f"{tcp}: must be an object.")
                r.ok = False
                continue
            title = tc.get("title")
            if not isinstance(title, str) or not title.strip():
                r.errors.append(f"{tcp}.title must be a non-empty string.")
                r.ok = False
            cat = tc.get("category")
            if not isinstance(cat, str) or cat not in VALID_CATEGORIES:
                r.errors.append(
                    f"{tcp}.category={cat!r} must be one of "
                    f"{VALID_CATEGORIES}."
                )
                r.ok = False
            pr = tc.get("priority")
            if pr is not None and (
                not isinstance(pr, str) or pr not in VALID_PRIORITIES
            ):
                r.errors.append(
                    f"{tcp}.priority={pr!r} must be one of "
                    f"{VALID_PRIORITIES} or omitted."
                )
                r.ok = False
            steps = tc.get("steps")
            if not isinstance(steps, list) or not steps:
                r.errors.append(f"{tcp}.steps must be a non-empty list.")
                r.ok = False
                continue
            for si2, st in enumerate(steps):
                if not isinstance(st, dict):
                    r.errors.append(
                        f"{tcp}.steps[{si2}]: must be an object."
                    )
                    r.ok = False
                    continue
                if not isinstance(st.get("action"), str) or \
                   not st["action"].strip():
                    r.errors.append(
                        f"{tcp}.steps[{si2}].action must be non-empty."
                    )
                    r.ok = False
                if not isinstance(st.get("expected"), str):
                    r.errors.append(
                        f"{tcp}.steps[{si2}].expected must be a string."
                    )
                    r.ok = False
            r.n_test_cases += 1
    return r
