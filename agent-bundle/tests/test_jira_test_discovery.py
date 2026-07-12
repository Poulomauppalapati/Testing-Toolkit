"""Regression tests for versatile JIRA linked-test-case discovery.

Exercises jira.boards._parse_issue: test coverage can be modelled as issue
links (by link-type name or linked issue type) OR as subtasks, and Xray/Zephyr
issue types ("Test", "Test Execution", "Test Set") must all be recognised. The
count is de-duplicated by issue key.
"""
from __future__ import annotations

from jira import boards


def _link(link_name: str, key: str, itype: str) -> dict:
    return {
        "type": {"name": link_name},
        "outwardIssue": {"key": key, "fields": {"issuetype": {"name": itype}}},
    }


def _subtask(key: str, itype: str) -> dict:
    return {"key": key, "fields": {"issuetype": {"name": itype}}}


def _issue(**field_overrides: object) -> dict:
    fields: dict[str, object] = {
        "summary": "S", "issuetype": {"name": "Story"},
        "status": {"name": "Open"},
    }
    fields.update(field_overrides)
    return {"key": "PROJ-1", "id": "1", "fields": fields}


def test_counts_links_by_linked_type_and_link_name() -> None:
    raw = _issue(issuelinks=[
        _link("Tests", "T-1", "Bug"),          # matched by link-type name
        _link("Relates", "T-2", "Test Case"),  # matched by linked issue type
        _link("Blocks", "S-9", "Story"),       # not a test -> ignored
    ])
    assert boards._parse_issue(raw).test_case_count == 2


def test_counts_xray_zephyr_test_types() -> None:
    raw = _issue(issuelinks=[
        _link("Relates", "X-1", "Test"),
        _link("Relates", "X-2", "Test Execution"),
        _link("Relates", "X-3", "Test Set"),
    ])
    assert boards._parse_issue(raw).test_case_count == 3


def test_counts_test_subtasks() -> None:
    raw = _issue(subtasks=[
        _subtask("SUB-1", "Test"),
        _subtask("SUB-2", "Sub-task"),  # not a test -> ignored
    ])
    assert boards._parse_issue(raw).test_case_count == 1


def test_dedups_link_and_subtask_same_key() -> None:
    raw = _issue(
        issuelinks=[_link("Tests", "DUP-1", "Test")],
        subtasks=[_subtask("DUP-1", "Test")],
    )
    # Same key reached both ways -> counted once.
    assert boards._parse_issue(raw).test_case_count == 1


def test_no_tests_is_zero() -> None:
    raw = _issue(issuelinks=[_link("Blocks", "S-9", "Story")])
    assert boards._parse_issue(raw).test_case_count == 0
