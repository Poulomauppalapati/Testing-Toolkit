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

_MAX_INPUT_CHARS: Final[int] = 80000
_MAX_TOKENS: Final[int] = 4096

_EXTRACTION_SYSTEM: Final[str] = (
    "You are a Senior QA analyst building a mental model of a system under "
    "test. Given project documentation excerpts, extract a structured "
    "understanding. Be exhaustive but only state what is explicitly in the "
    "documents. Do NOT invent or assume anything not stated. Output valid "
    "JSON only, no prose, no code fence."
)

_EXTRACTION_USER_TEMPLATE: Final[str] = """\
Analyze the following project documentation and extract:

1. ACTORS: Who uses this system? List each role/persona and their key permissions or responsibilities.
2. ENTITIES: What are the key business data objects? (e.g., "Assessment", "Task", "Order")
3. WORKFLOWS: What are the main business processes? For each, list the states/transitions if described.
4. INTEGRATIONS: What external systems, APIs, or batch jobs does this system connect to?
5. BUSINESS_RULES: What validation rules, constraints, thresholds, or conditions are explicitly stated?
6. SCREENS: What UI pages/screens/dialogs are mentioned? What is each for?
7. TEST_DATA_NEEDS: What types of test data would a tester need to exercise this system?

Output as a JSON object with exactly these 7 keys. Each value is a list of objects with "name" and "description" fields.
Example format:
{{"actors": [{{"name": "Admin", "description": "Full system access, manages users and configuration"}}], ...}}

If a category has no information in the documents, return an empty list for that key.

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
    # Metadata
    extracted_at: float = 0.0
    kb_fingerprint: str = ""

    def is_empty(self) -> bool:
        return not any([
            self.actors, self.entities, self.workflows,
            self.integrations, self.business_rules,
            self.screens, self.test_data_needs,
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
