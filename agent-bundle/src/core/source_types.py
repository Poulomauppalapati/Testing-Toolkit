"""Shared dataclasses for multi-source project management (ADO + JIRA)."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SourceType(Enum):
    """Supported project source backends."""

    ADO = "ado"
    JIRA = "jira"


@dataclass(slots=True)
class SourceConfig:
    """Connection config for a single project source."""

    source_type: SourceType
    url: str
    user: str  # empty for ADO
    pat: str
    project_prefix: str


@dataclass(slots=True)
class ProjectInfo:
    """Resolved project entry with source metadata."""

    name: str  # full project name
    source_type: SourceType
    display_name: str


SOURCE_SUFFIXES: dict[SourceType, str] = {
    SourceType.ADO: " - ADO",
    SourceType.JIRA: " - JIRA",
}


def append_source_suffix(name: str, source: SourceType) -> str:
    """Append the source-type suffix to a project name."""
    return name + SOURCE_SUFFIXES[source]


def strip_source_suffix(name: str) -> tuple[str, SourceType]:
    """Strip known suffix, return bare name + detected type.

    If no suffix found, returns (name, SourceType.ADO) as default.
    """
    for source_type, suffix in SOURCE_SUFFIXES.items():
        if name.endswith(suffix):
            return name[: -len(suffix)], source_type
    return name, SourceType.ADO
