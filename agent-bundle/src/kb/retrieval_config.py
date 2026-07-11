"""Typed, per-project knowledge-base retrieval configuration."""

from __future__ import annotations

import fnmatch
import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Final

CONFIG_NAME: Final[str] = "kb_retrieval.json"
SCHEMA_VERSION: Final[int] = 2


@dataclass(frozen=True, slots=True)
class RetrievalConfig:
    target_chunk_tokens: int = 700
    max_chunk_tokens: int = 900
    overlap_tokens: int = 100
    fetch_k: int = 96
    final_k: int = 8
    min_semantic_score: float = 0.20
    semantic_weight: float = 0.55
    lexical_weight: float = 0.15
    reranker_weight: float = 0.20
    source_priority_weight: float = 0.10
    duplicate_cosine_threshold: float = 0.94
    mmr_lambda: float = 0.78
    per_source_cap: int = 2
    neutral_priority: float = 0.50
    source_priorities: dict[str, float] = field(default_factory=dict)
    role_priorities: dict[str, float] = field(default_factory=dict)

    def priority_for(self, source: str, role: str) -> float:
        matches = [
            float(value)
            for pattern, value in self.source_priorities.items()
            if fnmatch.fnmatch(source.lower(), pattern.lower())
        ]
        if matches:
            return max(0.0, min(1.0, max(matches)))
        value = self.role_priorities.get(role, self.neutral_priority)
        return max(0.0, min(1.0, float(value)))

    def fingerprint(self) -> str:
        payload = {"schema": SCHEMA_VERSION, **asdict(self)}
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("ascii")).hexdigest()[:16]


def _bounded_int(value: Any, default: int, low: int, high: int) -> int:
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default


def _bounded_float(value: Any, default: float) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def load_retrieval_config(project_root: Path | None = None) -> RetrievalConfig:
    defaults = RetrievalConfig()
    data: dict[str, Any] = {}
    path = project_root / CONFIG_NAME if project_root is not None else None
    if path is not None and path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
        except (OSError, json.JSONDecodeError):
            data = {}
    target = _bounded_int(data.get("target_chunk_tokens"), defaults.target_chunk_tokens, 128, 4096)
    maximum = _bounded_int(data.get("max_chunk_tokens"), defaults.max_chunk_tokens, target, 8192)
    overlap = _bounded_int(data.get("overlap_tokens"), defaults.overlap_tokens, 0, target // 2)
    return RetrievalConfig(
        target_chunk_tokens=target,
        max_chunk_tokens=maximum,
        overlap_tokens=overlap,
        fetch_k=_bounded_int(data.get("fetch_k"), defaults.fetch_k, 8, 1000),
        final_k=_bounded_int(data.get("final_k"), defaults.final_k, 1, 100),
        min_semantic_score=_bounded_float(data.get("min_semantic_score"), defaults.min_semantic_score),
        semantic_weight=_bounded_float(data.get("semantic_weight"), defaults.semantic_weight),
        lexical_weight=_bounded_float(data.get("lexical_weight"), defaults.lexical_weight),
        reranker_weight=_bounded_float(data.get("reranker_weight"), defaults.reranker_weight),
        source_priority_weight=_bounded_float(data.get("source_priority_weight"), defaults.source_priority_weight),
        duplicate_cosine_threshold=_bounded_float(data.get("duplicate_cosine_threshold"), defaults.duplicate_cosine_threshold),
        mmr_lambda=_bounded_float(data.get("mmr_lambda"), defaults.mmr_lambda),
        per_source_cap=_bounded_int(data.get("per_source_cap"), defaults.per_source_cap, 1, 100),
        neutral_priority=_bounded_float(data.get("neutral_priority"), defaults.neutral_priority),
        source_priorities={str(k): _bounded_float(v, defaults.neutral_priority) for k, v in dict(data.get("source_priorities") or {}).items()},
        role_priorities={str(k): _bounded_float(v, defaults.neutral_priority) for k, v in dict(data.get("role_priorities") or {}).items()},
    )


def document_role(path: Path) -> str:
    suffix = path.suffix.lower().lstrip(".")
    return suffix or "unknown"
