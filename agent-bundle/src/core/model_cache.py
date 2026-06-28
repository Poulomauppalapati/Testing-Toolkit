"""
model_cache.py
Local cache for the "working models" list.

Probing every catalog model with a 1-token request (list_working_models)
is the slow part of opening the connection dialog: it can take many
seconds against a corporate gateway. The list almost never changes between
launches, so we cache it on the agent and reuse it instantly.

Design (matches the agreed behaviour):
  * Cached on the agent, in the TestingToolkitWeb workspace.
  * Auto-used: the dropdown populates immediately from cache.
  * Manual refresh: a "Fetch models" click re-probes and overwrites.
  * Invalidated automatically when the base URL or API key changes -- the
    cache is keyed by a salted fingerprint of (base_url, api_key) so a new
    endpoint/key never serves a stale list. The raw key is NEVER stored;
    only a one-way hash of it is.

The file is best-effort: any read/write error degrades to "no cache", so
model listing still works (just without the speed-up).
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Final

from core.app_config import WORKSPACE

_CACHE_PATH: Final[Path] = WORKSPACE / "models_cache.json"
_SCHEMA: Final[int] = 1
# Salt so the on-disk fingerprint cannot be reversed into the key/url.
_FINGERPRINT_SALT: Final[str] = "testing-toolkit-models-cache/v1"


def cache_path() -> Path:
    return _CACHE_PATH


def fingerprint(base_url: str, api_key: str) -> str:
    """One-way fingerprint of the connection identity. Changing either the
    base URL or the key produces a different fingerprint, which invalidates
    the cache automatically."""
    h = hashlib.sha256()
    h.update(_FINGERPRINT_SALT.encode("utf-8"))
    h.update(b"\x00")
    h.update((base_url or "").strip().encode("utf-8"))
    h.update(b"\x00")
    h.update((api_key or "").encode("utf-8"))
    return h.hexdigest()


def load(base_url: str, api_key: str) -> list[dict[str, str]] | None:
    """Return the cached model list for this connection, or None if there is
    no cache, it is for a different base URL/key, or it is unreadable."""
    try:
        if not _CACHE_PATH.exists():
            return None
        data = json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    if int(data.get("schema", 0)) != _SCHEMA:
        return None
    if str(data.get("fingerprint", "")) != fingerprint(base_url, api_key):
        return None
    models = data.get("models")
    if not isinstance(models, list):
        return None
    out: list[dict[str, str]] = []
    for m in models:
        if isinstance(m, dict) and m.get("id"):
            out.append({
                "id": str(m.get("id", "")),
                "provider": str(m.get("provider", "")),
                "label": str(m.get("label", "")) or str(m.get("id", "")),
            })
    return out or None


def save(
    base_url: str, api_key: str, models: list[dict[str, str]]
) -> bool:
    """Persist the working-model list for this connection. Best-effort."""
    payload: dict[str, Any] = {
        "schema": _SCHEMA,
        "fingerprint": fingerprint(base_url, api_key),
        "cached_at": time.time(),
        "models": models,
    }
    try:
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = _CACHE_PATH.with_name(_CACHE_PATH.name + ".tmp")
        tmp.write_text(
            json.dumps(payload, ensure_ascii=True), encoding="utf-8"
        )
        tmp.replace(_CACHE_PATH)
        return True
    except OSError:
        return False


def clear() -> None:
    """Drop the cache (e.g. on explicit disconnect). Never raises."""
    try:
        _CACHE_PATH.unlink(missing_ok=True)
    except OSError:
        pass
