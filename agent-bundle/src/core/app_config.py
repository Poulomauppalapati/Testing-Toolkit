"""
app_config.py
Hardcoded identity, workspace paths, and defaults for the Testing
Toolkit. Charan's convention: no argparse, no .env files; the constants
live near the top of this module. Change them, restart the app.

Workspace layout (created on first launch):
    ~/TestingToolkitWeb/   (override with TT_WORKSPACE_DIR)
        projects/<full_project_name>/   per-project KB + system prompt
            system_prompt.txt
            kb/                          drop requirement docs here
            kb_index.json                cached deterministic chunk index
            generated/                   payloads + review xlsx per run
        runs/                            packager work + outputs
        logs/                            rotating debug log
        ui_prefs.json                    theme + window + splitter state
        settings.json                    base url, model, org, prefix
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Final

# -------------------------- IDENTITY --------------------------
APP_NAME:    Final[str] = "Testing Toolkit"
APP_SLUG:    Final[str] = "TestingToolkit"
APP_VERSION: Final[str] = "2.0.0"

# The web build keeps its workspace separate from the desktop app so the
# two can coexist on the same machine. Everything (projects, KB, runs,
# outputs/artifacts, logs, settings) lives under this single root.
WEB_WORKSPACE_SLUG: Final[str] = "TestingToolkitWeb"


def _resolve_workspace() -> Path:
    """Workspace root for the web agent.

    Defaults to ``~/TestingToolkitWeb`` (e.g. ``C:\\Users\\cnr002\\
    TestingToolkitWeb`` on Windows). Set the ``TT_WORKSPACE_DIR``
    environment variable to override it with an absolute path.
    """
    override = (os.environ.get("TT_WORKSPACE_DIR") or "").strip()
    if override:
        try:
            return Path(override).expanduser()
        except (OSError, ValueError):
            pass
    return Path.home() / WEB_WORKSPACE_SLUG

# -------------------------- WORKSPACE -------------------------
WORKSPACE:    Final[Path] = _resolve_workspace()
PROJECTS_DIR: Final[Path] = WORKSPACE / "projects"
RUNS_DIR:     Final[Path] = WORKSPACE / "runs"
OUTPUTS_DIR:  Final[Path] = WORKSPACE / "outputs"
LOGS_DIR:     Final[Path] = WORKSPACE / "logs"

UI_PREFS_PATH: Final[Path] = WORKSPACE / "ui_prefs.json"
SETTINGS_PATH: Final[Path] = WORKSPACE / "settings.json"

# -------------------------- DISPLAY ---------------------------
# Projects are shown with this prefix stripped, e.g.
# "InteractionsHub_Abbott" -> "Abbott". Stored full name is used for
# every API call; only the displayed label is shortened.
DEFAULT_PROJECT_PREFIX: Final[str] = "InteractionsHub_"

# -------------------------- WINDOW ----------------------------
DEFAULT_WINDOW_W: Final[int] = 1480
DEFAULT_WINDOW_H: Final[int] = 920

# -------------------------- LLM API --------------------------
# base_url is configurable (an enterprise gateway / proxy may sit in
# front of the LLM API). The Messages API path is appended by the
# client, so store only the origin here.
DEFAULT_LLM_BASE_URL: Final[str] = "https://api.anthropic.com"
LLM_API_VERSION:      Final[str] = "2025-04-15"

# Primary model drives test-case generation (quality matters).
DEFAULT_MODEL: Final[str] = "bedrock.anthropic.claude-opus-4-6"
# Fast model for the recursive retrieval map steps.
DEFAULT_FAST_MODEL: Final[str] = "bedrock.anthropic.claude-sonnet-4-6"
# Safety fallback model used when primary/fast fail or rate-limit.
DEFAULT_FALLBACK_MODEL: Final[str] = "bedrock.anthropic.claude-haiku-4-5"

# Backwards-compat aliases (internal imports that use old names)
DEFAULT_ANTHROPIC_BASE_URL = DEFAULT_LLM_BASE_URL
ANTHROPIC_VERSION = LLM_API_VERSION

# Env-overridable LLM endpoint + key. Primary source is settings_store
# (per-user settings.json); these act as the fallback when settings has no
# value. Callers use e.g. `(load_api_key() or "").strip() or LLM_API_KEY`.
LLM_BASE_URL: Final[str] = (os.environ.get("BASE_URL") or "").strip() or DEFAULT_LLM_BASE_URL
LLM_API_KEY:  Final[str] = (os.environ.get("API_KEY") or "").strip()

# --- Model capability tiers (consumed by core.model_router) ---
# Tiers map onto the three defaults above so behavior is unchanged unless a
# deployment overrides them via env. LARGE=quality, MEDIUM=balanced, SMALL=cheap.
MODEL_LARGE:  Final[str] = (os.environ.get("MODEL_LARGE") or "").strip() or DEFAULT_MODEL
MODEL_MEDIUM: Final[str] = (os.environ.get("MODEL_MEDIUM") or "").strip() or DEFAULT_FAST_MODEL
MODEL_SMALL:  Final[str] = (os.environ.get("MODEL_SMALL") or "").strip() or DEFAULT_FALLBACK_MODEL

# Optional per-task overrides. Empty by default -> model_router falls back to
# the tier model. Set these in env to pin a specific task to a specific model
# (e.g. a cheaper non-Anthropic model for reranking/contextualization).
MODEL_RERANK:       Final[str] = (os.environ.get("MODEL_RERANK") or "").strip()
MODEL_CONTEXTUALIZE: Final[str] = (os.environ.get("MODEL_CONTEXTUALIZE") or "").strip()
MODEL_EXTRACT:      Final[str] = (os.environ.get("MODEL_EXTRACT") or "").strip()
MODEL_GENERATE:     Final[str] = (os.environ.get("MODEL_GENERATE") or "").strip()
MODEL_CHAT:         Final[str] = (os.environ.get("MODEL_CHAT") or "").strip()
MODEL_OCR:          Final[str] = (os.environ.get("MODEL_OCR") or "").strip()

# --- Embedding model (consumed by kb.embeddings API embedder) ---
# API-based embeddings (matches desktop). Override via env for a different
# embedding model/dimension.
EMBED_MODEL: Final[str] = (os.environ.get("EMBED_MODEL") or "").strip() or "azure.text-embedding-3-small"
EMBED_DIM:   Final[int] = int((os.environ.get("EMBED_DIM") or "").strip() or "512")

# Token budgets for the Recursive Language Model (approximate; we count
# characters at ~4 chars/token). If the whole project KB fits under
# RLM_DIRECT_CONTEXT_TOKENS it is passed in one shot; otherwise the
# recursive navigate/map/reduce path is taken.
RLM_DIRECT_CONTEXT_TOKENS: Final[int] = 150_000
RLM_MAP_CHUNK_TOKENS:      Final[int] = 6_000
RLM_GENERATE_MAX_TOKENS:   Final[int] = 16_000
RLM_NAVIGATE_MAX_TOKENS:   Final[int] = 1_500
RLM_MAP_MAX_TOKENS:        Final[int] = 2_000


# Requirement decomposition: max output tokens for the fast model to
# enumerate atomic testable requirements before generation.
RLM_DECOMPOSE_MAX_TOKENS:  Final[int] = 2_000

# Coverage verification + gap-fill pass: max output tokens for the
# post-generation verification call.
RLM_VERIFY_MAX_TOKENS:     Final[int] = 8_000

# Regeneration: maximum number of user-driven regeneration iterations
# per session per set of work items.
RLM_MAX_REGEN_ITERATIONS:  Final[int] = 10


# -------------------------- KB INDEXING -----------------------
# The first index build is the slow part of the first generation. We run it
# "full BRRRR": files are extracted/OCR'd/contextualized across a worker pool
# so a capable PC saturates its CPU and IO instead of crawling one file at a
# time. Quality is unchanged (same deterministic chunk ids, same checkpoint).
def _resolve_int_env(name: str, default: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    if raw:
        try:
            return max(0, int(raw))
        except ValueError:
            pass
    return default


# Number of files processed in parallel during indexing.
#   0 = auto -> use every logical CPU core (full utilization).
# Override with TT_KB_INDEX_WORKERS (e.g. set to 4 to cap on a small box).
KB_INDEX_MAX_WORKERS: Final[int] = _resolve_int_env("TT_KB_INDEX_WORKERS", 0)

# Max concurrent contextual-retrieval LLM calls per document. Raising this
# pushes the gateway harder; lower it if you hit rate limits.
# Override with TT_KB_CONTEXT_CONCURRENCY.
KB_CONTEXTUAL_CONCURRENCY: Final[int] = _resolve_int_env(
    "TT_KB_CONTEXT_CONCURRENCY", 8
)


def resolve_index_workers(n_items: int) -> int:
    """Effective worker count for an indexing run of ``n_items`` files."""
    configured = KB_INDEX_MAX_WORKERS or (os.cpu_count() or 4)
    if n_items <= 0:
        return 1
    return max(1, min(configured, n_items))


def ensure_workspace() -> None:
    """Create the workspace skeleton. Idempotent, never raises."""
    for d in (WORKSPACE, PROJECTS_DIR, RUNS_DIR, OUTPUTS_DIR, LOGS_DIR):
        try:
            d.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass


def display_project_name(full_name: str, prefix: str) -> str:
    """Strip the configured prefix for display. Case-insensitive on the
    prefix; falls back to the full name if stripping would empty it."""
    if prefix and full_name.lower().startswith(prefix.lower()):
        stripped = full_name[len(prefix):].strip()
        return stripped or full_name
    return full_name


def _base_dir() -> Path:
    """Directory that holds bundled assets. Works both from source and
    from a PyInstaller bundle (sys._MEIPASS)."""
    mei = getattr(sys, "_MEIPASS", "")
    if mei:
        return Path(mei)
    return Path(__file__).resolve().parent


def asset_path(name: str) -> Path:
    """Absolute path to a bundled asset under assets/."""
    return _base_dir() / "assets" / name


def icon_path() -> str:
    """Best available app icon path, or '' if none is present."""
    for name in ("icon.png", "icon_64.png", "icon.ico"):
        p = asset_path(name)
        if p.exists():
            return str(p)
    return ""
