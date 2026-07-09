"""
context_summary.py
Project-level context extraction from KB documents.

After indexing, produces a structured "project context summary" that
captures the Senior QA's mental model of the system under test: actors,
entities, workflows, integrations, business rules, screens, and test data
needs. This summary is injected into the generation prompt so the LLM
starts with deep domain understanding rather than discovering it per-run.

The extraction is optional (requires an LLM client) and gracefully skips
when unavailable. Results are cached to context_summary.json and only
regenerated when the KB index changes.

ASCII-only; fully type-hinted.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Final

LogFn = Callable[[str], None]

# Deep-context budgets. Large on purpose: the goal is a thorough, whole-project
# mental model, not a shallow summary. ~200k chars (~50k tokens) of source with
# up to 8k tokens of structured output comfortably fits modern gateway models.
_MAX_INPUT_CHARS: Final[int] = 200000
_MAX_TOKENS: Final[int] = 8192

_EXTRACTION_SYSTEM: Final[str] = (
    "You are a Principal QA architect building a COMPLETE, in-depth mental "
    "model of a system under test from its documentation. Your goal is total "
    "coverage: capture every actor, entity, workflow, rule, screen, "
    "integration, edge case, dependency, and domain term the documents "
    "describe -- leave nothing material out. Write rich, specific, "
    "multi-sentence descriptions that a tester could act on directly (include "
    "concrete values, thresholds, state names, field names, and conditions "
    "verbatim where stated). Be exhaustive, but state ONLY what is explicitly "
    "supported by the documents -- never invent, assume, or generalize beyond "
    "the text. Output valid JSON only: no prose, no markdown, no code fence."
)

_EXTRACTION_USER_TEMPLATE: Final[str] = """\
Analyze the following project documentation and extract a DEEP, EXHAUSTIVE
model of the entire system. For each category list EVERY distinct item the
documents describe (do not cap the count), each with a detailed, specific
description grounded in the text:

1. ACTORS: Every role/persona/user type. Describe permissions, responsibilities, and what each can and cannot do.
2. ENTITIES: Every key business data object (e.g., "Assessment", "Order"). Describe its important fields, identifiers, and relationships to other entities.
3. WORKFLOWS: Every business process. Describe the ordered steps, all states, and every transition/trigger/guard condition mentioned.
4. INTEGRATIONS: Every external system, API, file feed, batch job, or service. Describe direction of data flow, trigger/schedule, and payload if stated.
5. BUSINESS_RULES: Every validation rule, constraint, threshold, calculation, or condition. Quote exact numbers, limits, and formulas verbatim.
6. SCREENS: Every UI page/screen/dialog/tab. Describe its purpose, key fields/controls, and the actions available on it.
7. TEST_DATA_NEEDS: Every kind of test data required to exercise the system, including specific data shapes, seed records, and preconditions.
8. EDGE_CASES: Every explicitly stated edge case, boundary, negative/error path, failure mode, or exception-handling behavior.
9. NON_FUNCTIONAL: Every non-functional requirement -- performance, security, access control, compliance/regulatory, availability, accessibility, auditing.
10. DEPENDENCIES: Every sequencing/ordering dependency, precondition, upstream/downstream data flow, and cross-module or cross-team dependency.
11. GLOSSARY: Every domain term, acronym, abbreviation, status code, or product-specific name, with its precise meaning as used in the documents.

Output a JSON object with EXACTLY these 11 keys (lowercase): actors, entities,
workflows, integrations, business_rules, screens, test_data_needs, edge_cases,
non_functional, dependencies, glossary. Each value is a list of objects with
"name" and "description" fields.
Example format:
{{"actors": [{{"name": "Admin", "description": "Full system access; manages users, configuration, and role assignments. Cannot delete audit records."}}], ...}}

If a category truly has no information in the documents, return an empty list
for that key. Prefer more items with richer descriptions over fewer.

<documents>
{context}
</documents>"""


@dataclass(slots=True)
class ContextItem:
    """Single extracted context item (role, entity, screen, etc.)."""
    name: str
    description: str


@dataclass(slots=True)
class ProjectContext:
    """Structured project understanding extracted from KB documents."""
    actors: list[ContextItem] = field(default_factory=list)
    entities: list[ContextItem] = field(default_factory=list)
    workflows: list[ContextItem] = field(default_factory=list)
    integrations: list[ContextItem] = field(default_factory=list)
    business_rules: list[ContextItem] = field(default_factory=list)
    screens: list[ContextItem] = field(default_factory=list)
    test_data_needs: list[ContextItem] = field(default_factory=list)
    edge_cases: list[ContextItem] = field(default_factory=list)
    non_functional: list[ContextItem] = field(default_factory=list)
    dependencies: list[ContextItem] = field(default_factory=list)
    glossary: list[ContextItem] = field(default_factory=list)
    # Metadata
    extracted_at: float = 0.0
    kb_fingerprint: str = ""

    def is_empty(self) -> bool:
        return not any([
            self.actors, self.entities, self.workflows,
            self.integrations, self.business_rules,
            self.screens, self.test_data_needs,
            self.edge_cases, self.non_functional,
            self.dependencies, self.glossary,
        ])

    def to_prompt_section(self) -> str:
        """Format as a prompt injection section for the generation model."""
        if self.is_empty():
            return ""
        parts: list[str] = ["PROJECT CONTEXT SUMMARY", "=" * 40]
        sections = [
            ("ACTORS/ROLES", self.actors),
            ("BUSINESS ENTITIES", self.entities),
            ("WORKFLOWS", self.workflows),
            ("INTEGRATION POINTS", self.integrations),
            ("BUSINESS RULES", self.business_rules),
            ("SCREENS/PAGES", self.screens),
            ("TEST DATA NEEDS", self.test_data_needs),
            ("EDGE CASES / NEGATIVE PATHS", self.edge_cases),
            ("NON-FUNCTIONAL REQUIREMENTS", self.non_functional),
            ("DEPENDENCIES / DATA FLOWS", self.dependencies),
            ("GLOSSARY / TERMINOLOGY", self.glossary),
        ]
        for title, items in sections:
            if items:
                parts.append(f"\n{title}:")
                for item in items:
                    parts.append(f"  - {item.name}: {item.description}")
        parts.append("")
        return "\n".join(parts)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProjectContext":
        """Reconstruct from a saved dict (context_summary.json)."""
        def _parse_items(raw: Any) -> list[ContextItem]:
            if not isinstance(raw, list):
                return []
            out: list[ContextItem] = []
            for item in raw:
                if isinstance(item, dict):
                    out.append(ContextItem(
                        name=str(item.get("name", "")),
                        description=str(item.get("description", "")),
                    ))
            return out

        return cls(
            actors=_parse_items(data.get("actors")),
            entities=_parse_items(data.get("entities")),
            workflows=_parse_items(data.get("workflows")),
            integrations=_parse_items(data.get("integrations")),
            business_rules=_parse_items(data.get("business_rules")),
            screens=_parse_items(data.get("screens")),
            test_data_needs=_parse_items(data.get("test_data_needs")),
            edge_cases=_parse_items(data.get("edge_cases")),
            non_functional=_parse_items(data.get("non_functional")),
            dependencies=_parse_items(data.get("dependencies")),
            glossary=_parse_items(data.get("glossary")),
            extracted_at=float(data.get("extracted_at", 0.0)),
            kb_fingerprint=str(data.get("kb_fingerprint", "")),
        )


def _build_document_text(kb_index: Any) -> str:
    """Assemble representative text from the KB index for extraction.
    Uses chunk titles and first portion of each chunk's text, up to the
    character budget."""
    parts: list[str] = []
    total = 0
    # kb_index.chunks is a list of KbChunk(id, doc, title, text, context)
    chunks = getattr(kb_index, "chunks", [])
    for chunk in chunks:
        title = getattr(chunk, "title", "") or ""
        text = getattr(chunk, "text", "") or ""
        ctx = getattr(chunk, "context", "") or ""
        entry = f"## {title}\n{ctx}\n{text}" if ctx else f"## {title}\n{text}"
        if total + len(entry) > _MAX_INPUT_CHARS:
            remaining = _MAX_INPUT_CHARS - total
            if remaining > 200:
                parts.append(entry[:remaining])
            break
        parts.append(entry)
        total += len(entry)
    return "\n\n".join(parts)


def _parse_llm_response(raw: str) -> dict[str, Any]:
    """Extract JSON from the LLM response, handling code fences."""
    import re
    text = raw.strip()
    # Strip code fence if present
    fence_match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()
    return json.loads(text)


async def extract_project_context_async(
    kb_index: Any,
    client: Any,
    model: str,
    kb_fingerprint: str = "",
    on_log: LogFn | None = None,
) -> ProjectContext:
    """Extract structured project context from the KB index using the LLM.

    Args:
        kb_index: A KbIndex instance with .chunks attribute.
        client: An AnthropicClient (or compatible) with .complete_async().
        model: Model ID string for the extraction call.
        kb_fingerprint: Hash identifying the current KB state.
        on_log: Optional logging callback.

    Returns:
        ProjectContext with extracted items. Empty on failure (graceful).
    """
    log = on_log or (lambda _: None)

    doc_text = _build_document_text(kb_index)
    if not doc_text.strip():
        log("[INFO] No KB content available for context extraction")
        return ProjectContext(kb_fingerprint=kb_fingerprint)

    user_prompt = _EXTRACTION_USER_TEMPLATE.format(context=doc_text)
    log("[INFO] Extracting project context from KB documents...")

    # Context extraction sends ~200k chars to the model and expects ~8k tokens
    # back. The default 120s timeout is too tight for large KBs on slower
    # gateways. Temporarily raise it for this call, then restore.
    original_timeout = getattr(client, "timeout_sec", 120.0)
    client.timeout_sec = max(original_timeout, 300.0)
    try:
        result = await client.complete_async(
            model=model,
            system=_EXTRACTION_SYSTEM,
            user=user_prompt,
            max_tokens=_MAX_TOKENS,
            temperature=0.0,
        )
        raw_text = getattr(result, "text", "") or ""
        data = _parse_llm_response(raw_text)
        ctx = ProjectContext.from_dict(data)
        ctx.extracted_at = time.time()
        ctx.kb_fingerprint = kb_fingerprint
        log(f"[SUCCESS] Project context extracted: "
            f"{len(ctx.actors)} actors, {len(ctx.entities)} entities, "
            f"{len(ctx.workflows)} workflows, {len(ctx.screens)} screens")
        return ctx
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        log(f"[WARN] Context extraction parse error: {exc!r}")
        return ProjectContext(kb_fingerprint=kb_fingerprint)
    except Exception as exc:  # noqa: BLE001
        log(f"[WARN] Context extraction failed (non-blocking): {exc!r}")
        return ProjectContext(kb_fingerprint=kb_fingerprint)
    finally:
        client.timeout_sec = original_timeout


def save_context_summary(path: Path, ctx: ProjectContext) -> bool:
    """Persist context summary to disk as JSON."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(ctx.to_dict(), indent=2, ensure_ascii=True),
            encoding="utf-8",
        )
        return True
    except OSError:
        return False


def load_context_summary(path: Path) -> ProjectContext | None:
    """Load a previously saved context summary. Returns None if missing
    or corrupt."""
    try:
        if not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        return ProjectContext.from_dict(data)
    except (OSError, json.JSONDecodeError, TypeError):
        return None
