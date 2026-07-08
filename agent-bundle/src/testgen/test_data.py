"""Pattern-based test data suggestions for test case steps."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class TestDataSuggestion:
    """Concrete test values for a detected field type."""

    field_name: str
    positive_values: list[str] = field(default_factory=list)
    negative_values: list[str] = field(default_factory=list)


# Pattern -> (field_name, positive_values, negative_values)
_FIELD_PATTERNS: list[tuple[re.Pattern[str], str, list[str], list[str]]] = [
    (
        re.compile(r"\b(e[-]?mail)\b", re.IGNORECASE),
        "email",
        ["user@example.com", "test.user+tag@domain.co.uk"],
        ["invalid", "@no-local.com", "missing-at.com", ""],
    ),
    (
        re.compile(r"\b(first\s*name|last\s*name|full\s*name|\bname\b)", re.IGNORECASE),
        "name",
        ["John Smith", "Jane"],
        ["", "A" * 256, "   "],
    ),
    (
        re.compile(r"\b(phone|mobile|tel)\b", re.IGNORECASE),
        "phone",
        ["+1234567890", "0412345678"],
        ["abc", "12", ""],
    ),
    (
        re.compile(r"\b(amount|price|cost|total|fee)\b", re.IGNORECASE),
        "amount",
        ["100.00", "0.01", "9999.99"],
        ["-1", "abc", ""],
    ),
    (
        re.compile(r"\b(date|dob|birth\s*date)\b", re.IGNORECASE),
        "date",
        ["2025-01-15", "01/01/2000"],
        ["99/99/9999", "abc", ""],
    ),
    (
        re.compile(r"\b(password|passcode|pin)\b", re.IGNORECASE),
        "password",
        ["P@ssw0rd123!", "Str0ng!Pass"],
        ["", "short", "a" * 256],
    ),
    (
        re.compile(r"\b(url|link|website|href)\b", re.IGNORECASE),
        "url",
        ["https://example.com", "http://test.org/path?q=1"],
        ["not-a-url", "ftp://", ""],
    ),
    (
        re.compile(r"\b(number|count|quantity|qty|age)\b", re.IGNORECASE),
        "number",
        ["1", "100", "999"],
        ["0", "-1", "abc"],
    ),
    (
        re.compile(r"\b(dropdown|select|combo)\b", re.IGNORECASE),
        "dropdown",
        ["Select valid option", "First available option"],
        ["Leave unselected", "Non-existent option"],
    ),
]

# Actions that signal data entry
_ENTRY_VERBS: re.Pattern[str] = re.compile(
    r"\b(enter|input|fill|type|provide|set|specify|write)\b", re.IGNORECASE
)


def suggest_test_data(step_action: str) -> list[TestDataSuggestion]:
    """Pattern-match field types in a step action and return suggestions."""
    suggestions: list[TestDataSuggestion] = []
    for pattern, name, pos, neg in _FIELD_PATTERNS:
        if pattern.search(step_action):
            suggestions.append(TestDataSuggestion(
                field_name=name,
                positive_values=list(pos),
                negative_values=list(neg),
            ))
    return suggestions


def enrich_payload(payload: dict) -> dict:  # type: ignore[type-arg]
    """Add 'test_data' key to each step that has data entry actions.

    Expects payload with a 'steps' list of dicts, each having an 'action' key.
    Returns the same payload mutated in place (also returned for chaining).
    """
    steps: list[dict] = payload.get("steps", [])  # type: ignore[type-arg]
    for step in steps:
        action: str = step.get("action", "")
        if not _ENTRY_VERBS.search(action):
            continue
        suggestions = suggest_test_data(action)
        if suggestions:
            step["test_data"] = [
                {
                    "field": s.field_name,
                    "positive": s.positive_values,
                    "negative": s.negative_values,
                }
                for s in suggestions
            ]
    return payload
