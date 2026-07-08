"""
guardrails.py
Lightweight input pre-filter for off-topic request detection.
Runs BEFORE the LLM call to save tokens on obviously off-topic queries.
"""
from __future__ import annotations

import re
from typing import Final

# Refusal message (single source of truth)
REFUSAL_MESSAGE: Final[str] = (
    "I can only assist with tasks related to your current project and testing "
    "activities. Please ask me something about your project requirements, "
    "test cases, or quality assurance work."
)

# Keywords that indicate testing/QA/project-related content
_ALLOWED_KEYWORDS: Final[frozenset[str]] = frozenset({
    "test", "testing", "qa", "quality", "bug", "defect", "requirement",
    "specification", "spec", "user story", "acceptance criteria", "scenario",
    "expected result", "actual result", "precondition", "postcondition",
    "regression", "smoke", "sanity", "integration", "e2e", "end to end",
    "unit test", "functional", "non-functional", "performance", "load",
    "stress", "security", "usability", "accessibility", "uat",
    "test case", "test step", "test plan", "test suite", "test run",
    "coverage", "traceability", "validation", "verification",
    "sprint", "iteration", "backlog", "work item", "task", "story",
    "epic", "feature", "release", "deployment", "ci", "cd", "pipeline",
    "build", "artifact", "environment", "staging", "production",
    "api", "endpoint", "request", "response", "payload", "status code",
    "database", "query", "schema", "migration", "field", "column",
    "login", "authentication", "authorization", "permission", "role",
    "ui", "ux", "button", "form", "page", "screen", "dialog", "modal",
    "navigation", "menu", "dropdown", "input", "output", "file",
    "upload", "download", "export", "import", "report", "dashboard",
    "generate", "create", "update", "delete", "edit", "modify",
    "review", "approve", "reject", "assign", "priority", "severity",
    "blocker", "critical", "major", "minor", "trivial",
    "ado", "azure devops", "board", "kanban", "scrum",
    "automation", "script", "framework", "selenium", "playwright",
    "assertion", "verify", "validate", "check", "confirm",
    "data", "boundary", "edge case", "negative", "positive",
    "error", "exception", "handling", "retry", "timeout",
    "document", "documentation", "template", "format",
    "project", "team", "stakeholder", "client", "customer",
})

# Pre-compiled pattern matching any allowed keyword with word boundaries.
# Sorted longest-first so multi-word phrases match before their sub-words.
_ALLOWED_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\b(?:" + "|".join(
        re.escape(kw) for kw in sorted(_ALLOWED_KEYWORDS, key=len, reverse=True)
    ) + r")\b",
    re.IGNORECASE,
)

# Patterns that are almost certainly off-topic
_OFFTOPIC_PATTERNS: Final[list[re.Pattern[str]]] = [
    re.compile(r"\b(weather|forecast|temperature|rain|sunny)\b", re.IGNORECASE),
    re.compile(r"\b(recipes?|cook(ing)?|ingredients?|bak(e|ing))\b", re.IGNORECASE),
    re.compile(r"\b(fibonacci|leetcode|hackerrank|dynamic programming)\b", re.IGNORECASE),
    re.compile(r"\b(poems?|poetry|songs?|lyrics|jokes?|riddles?)\b", re.IGNORECASE),
    re.compile(r"\b(stocks?|crypto|bitcoin|investments?|trading)\b", re.IGNORECASE),
    re.compile(r"\b(movies?|films?|tv show|netflix|anime|manga)\b", re.IGNORECASE),
    re.compile(r"\b(workouts?|exercises?|diet|calories|weight loss)\b", re.IGNORECASE),
    re.compile(r"\b(travel|vacations?|flights?|hotels?|tourist)\b", re.IGNORECASE),
    re.compile(r"\b(astrology|horoscopes?|zodiac)\b", re.IGNORECASE),
    re.compile(r"\b(translate|translation)\b.{0,20}\b(to|into)\s+\w+\b", re.IGNORECASE),
    re.compile(r"\b(who is|what is the capital|how tall|how old)\b", re.IGNORECASE),
    re.compile(r"\b(play|games?|chess|sudoku|trivia)\b", re.IGNORECASE),
]


def check_input_guardrail(user_message: str) -> str | None:
    """Check if user input is obviously off-topic.

    Returns None if the message passes (allowed through to LLM).
    Returns REFUSAL_MESSAGE if the message is clearly off-topic.

    This is a FAST pre-filter. When uncertain, it passes through
    (lets the LLM's system prompt handle edge cases).
    """
    msg_lower = user_message.lower().strip()

    # Very short messages or greetings - let through (could be project-related)
    if len(msg_lower) < 10:
        return None

    # Check for off-topic patterns first (fast rejection)
    for pattern in _OFFTOPIC_PATTERNS:
        if pattern.search(msg_lower):
            # But check if any allowed keyword is ALSO present
            # (e.g. "test the weather API" should pass)
            if _ALLOWED_PATTERN.search(msg_lower):
                return None
            return REFUSAL_MESSAGE

    # If message contains allowed keywords, it's fine
    if _ALLOWED_PATTERN.search(msg_lower):
        return None

    # For longer messages without any project keywords, let the LLM decide
    # (could be a complex requirement description without our specific keywords)
    return None
