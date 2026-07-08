"""
core/source_resolver.py
Web-agent glue that maps a (possibly suffixed) project name to its source
backend (ADO or JIRA) and the connection parameters needed to reach it.

The frontend passes full project names that may carry a source suffix
(" - ADO" / " - JIRA"), matching the desktop convention. This module strips
the suffix, decides the source, and hands back everything a route needs.

Kept deliberately small (YAGNI): no event bus, no cache layer -- just the
resolution a route actually needs.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.source_types import SourceType, strip_source_suffix


@dataclass(slots=True)
class ResolvedSource:
    """Everything a route needs to talk to one project's backend."""
    source: SourceType
    project: str            # bare project name / JIRA project key
    # ADO fields
    organization: str = ""
    # JIRA fields
    url: str = ""
    user: str = ""
    # shared secret
    pat: str = ""


def resolve_source(full_project: str) -> SourceType:
    """Return the source type for a (possibly suffixed) project name.

    Resolution order:
      1. Explicit suffix (" - JIRA" / " - ADO") wins.
      2. If only JIRA is configured, default unsuffixed names to JIRA.
      3. Otherwise default to ADO (the original single-source behavior).
    """
    bare, detected = strip_source_suffix(full_project)
    if full_project.endswith(" - JIRA") or full_project.endswith(" - ADO"):
        return detected

    from core.settings_store import is_jira_configured, is_configured

    jira_ok = is_jira_configured()
    ado_ok = is_configured()
    if jira_ok and not ado_ok:
        return SourceType.JIRA
    return SourceType.ADO


def resolve(full_project: str) -> ResolvedSource:
    """Resolve a full project name to its backend + connection params.

    Raises ValueError when the resolved source is not configured, with a
    message safe to surface to the user.
    """
    from core.settings_store import (
        get_setting,
        load_pat_value,
        load_jira_pat,
        is_jira_configured,
        KEY_ORG,
        KEY_JIRA_URL,
        KEY_JIRA_USER,
    )

    bare, _ = strip_source_suffix(full_project)
    source = resolve_source(full_project)

    if source is SourceType.JIRA:
        if not is_jira_configured():
            raise ValueError(
                "JIRA is not configured. Add the JIRA URL, username, and "
                "token in Settings."
            )
        return ResolvedSource(
            source=SourceType.JIRA,
            project=bare,
            url=get_setting(KEY_JIRA_URL),
            user=get_setting(KEY_JIRA_USER),
            pat=load_jira_pat(),
        )

    # Default: ADO
    pat = load_pat_value()
    org = get_setting(KEY_ORG)
    if not pat or not org:
        raise ValueError("PAT or organization not configured")
    return ResolvedSource(
        source=SourceType.ADO,
        project=bare,
        organization=org,
        pat=pat,
    )
