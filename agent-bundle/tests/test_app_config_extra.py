# Tests for core.app_config helper functions.
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest


# --------------------------------------------------------------------------
# _resolve_int_env: non-numeric string returns default
# --------------------------------------------------------------------------
def test_resolve_int_env_non_numeric(monkeypatch):
    from core.app_config import _resolve_int_env

    monkeypatch.setenv("TEST_VAR_NON_NUM", "abc")
    assert _resolve_int_env("TEST_VAR_NON_NUM", 42) == 42


# --------------------------------------------------------------------------
# _resolve_int_env: negative value clamped to 0
# --------------------------------------------------------------------------
def test_resolve_int_env_negative_clamped(monkeypatch):
    from core.app_config import _resolve_int_env

    monkeypatch.setenv("TEST_VAR_NEG", "-5")
    # max(0, int("-5")) == 0
    assert _resolve_int_env("TEST_VAR_NEG", 10) == 0


# --------------------------------------------------------------------------
# ensure_workspace creates all subdirectories
# --------------------------------------------------------------------------
def test_ensure_workspace_creates_dirs(tmp_path, monkeypatch):
    from core import app_config

    workspace = tmp_path / "TestWorkspace"
    projects = workspace / "projects"
    runs = workspace / "runs"
    outputs = workspace / "outputs"
    logs = workspace / "logs"

    with patch.object(app_config, "WORKSPACE", workspace), \
         patch.object(app_config, "PROJECTS_DIR", projects), \
         patch.object(app_config, "RUNS_DIR", runs), \
         patch.object(app_config, "OUTPUTS_DIR", outputs), \
         patch.object(app_config, "LOGS_DIR", logs):
        app_config.ensure_workspace()

    assert workspace.is_dir()
    assert projects.is_dir()
    assert runs.is_dir()
    assert outputs.is_dir()
    assert logs.is_dir()
