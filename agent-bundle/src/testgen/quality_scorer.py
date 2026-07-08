"""Rule-based quality scorer for generated test cases (P3)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class QualityScore:
    step_count_score: int = 0
    context_score: int = 0
    specificity_score: int = 0
    duplicate_score: int = 100  # 100 = no duplicates found
    overall: int = 0
    issues: list[str] = field(default_factory=list)


@dataclass
class PayloadQuality:
    scores: list[QualityScore] = field(default_factory=list)
    avg_score: float = 0.0
    below_threshold: int = 0  # count of TCs scoring < 60


# --- constants ---

_VAGUE_PHRASES: tuple[str, ...] = (
    "works as expected",
    "system behaves correctly",
    "no errors",
    "functions properly",
    "as designed",
)

_CONTEXT_KEYWORDS: tuple[str, ...] = (
    "page", "screen", "dialog", "modal", "panel", "tab", "section",
    "form", "menu", "popup", "window", "view", "dashboard",
)


# --- scoring helpers ---

def _score_step_count(steps: list[dict]) -> tuple[int, list[str]]:
    """Score step count. Target 8-15; <5 bad, >20 verbose."""
    n = len(steps)
    issues: list[str] = []
    if 8 <= n <= 15:
        score = 100
    elif 5 <= n < 8:
        score = 60 + (n - 5) * 13  # 60-99 ramp
    elif 15 < n <= 20:
        score = 100 - (n - 15) * 10  # 100-50 ramp
    elif n < 5:
        score = max(0, n * 12)
        issues.append(f"Too few steps ({n}); target is 8-15")
    else:  # > 20
        score = max(0, 50 - (n - 20) * 5)
        issues.append(f"Too many steps ({n}); target is 8-15")
    return score, issues


def _score_context(steps: list[dict]) -> tuple[int, list[str]]:
    """Every step should mention a screen/page context."""
    if not steps:
        return 0, ["No steps present"]
    hits = 0
    for s in steps:
        text = (s.get("action", "") + " " + s.get("expected", "")).lower()
        if any(kw in text for kw in _CONTEXT_KEYWORDS):
            hits += 1
    ratio = hits / len(steps)
    score = int(ratio * 100)
    issues: list[str] = []
    if ratio < 0.5:
        issues.append(f"Only {hits}/{len(steps)} steps mention screen/page context")
    return score, issues


def _score_specificity(steps: list[dict]) -> tuple[int, list[str]]:
    """Flag vague expected results."""
    if not steps:
        return 0, ["No steps present"]
    vague_count = 0
    issues: list[str] = []
    for s in steps:
        expected = s.get("expected", "").lower()
        for phrase in _VAGUE_PHRASES:
            if phrase in expected:
                vague_count += 1
                issues.append(f"Step {s.get('step', '?')}: vague expected result ('{phrase}')")
                break
    ratio = 1.0 - (vague_count / len(steps))
    return int(ratio * 100), issues


_WORD_RE = re.compile(r"[a-z0-9]+")


def _normalize_title(title: str) -> set[str]:
    """Lowercase, extract alphanumeric tokens."""
    return set(_WORD_RE.findall(title.lower()))


def _score_duplicates(tc: dict, all_tcs: list[dict]) -> tuple[int, list[str]]:
    """Set-overlap duplicate detection against other TCs in payload."""
    title = tc.get("title", "")
    tc_id = tc.get("id", "")
    words = _normalize_title(title)
    if not words:
        return 100, []

    issues: list[str] = []
    worst_overlap = 0.0
    for other in all_tcs:
        if other.get("id") == tc_id:
            continue
        other_words = _normalize_title(other.get("title", ""))
        if not other_words:
            continue
        intersection = words & other_words
        union = words | other_words
        overlap = len(intersection) / len(union) if union else 0.0
        if overlap > worst_overlap:
            worst_overlap = overlap

    # overlap >= 0.8 -> score 0; overlap <= 0.3 -> score 100
    if worst_overlap <= 0.3:
        score = 100
    elif worst_overlap >= 0.8:
        score = 0
        issues.append(f"Near-duplicate title detected (overlap {worst_overlap:.0%})")
    else:
        score = int(100 * (1.0 - (worst_overlap - 0.3) / 0.5))
        if worst_overlap >= 0.6:
            issues.append(f"Similar title detected (overlap {worst_overlap:.0%})")
    return score, issues


# --- public API ---

def score_test_case(tc: dict, all_tcs: list[dict] | None = None) -> QualityScore:
    """Score a single test case dict. Pass all_tcs for duplicate detection."""
    steps: list[dict] = tc.get("steps", [])
    all_tcs = all_tcs or []

    sc_score, sc_issues = _score_step_count(steps)
    ctx_score, ctx_issues = _score_context(steps)
    spec_score, spec_issues = _score_specificity(steps)
    dup_score, dup_issues = _score_duplicates(tc, all_tcs)

    issues = sc_issues + ctx_issues + spec_issues + dup_issues
    overall = int(0.30 * sc_score + 0.25 * ctx_score + 0.25 * spec_score + 0.20 * dup_score)

    return QualityScore(
        step_count_score=sc_score,
        context_score=ctx_score,
        specificity_score=spec_score,
        duplicate_score=dup_score,
        overall=overall,
        issues=issues,
    )


def score_payload(payload: dict) -> PayloadQuality:
    """Score all test cases in a payload. Expects payload['test_cases'] list."""
    tcs: list[dict] = payload.get("test_cases", [])
    scores: list[QualityScore] = [score_test_case(tc, tcs) for tc in tcs]
    avg = sum(s.overall for s in scores) / len(scores) if scores else 0.0
    below = sum(1 for s in scores if s.overall < 60)
    return PayloadQuality(scores=scores, avg_score=round(avg, 1), below_threshold=below)
