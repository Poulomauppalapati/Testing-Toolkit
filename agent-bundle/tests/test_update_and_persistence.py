"""Tests for the semantic update check and update-proof credential storage.

These lock in two guarantees the user asked for:
  1. Republishing a manifest at an equal/older version does NOT prompt a
     reinstall (only a strictly-newer version does).
  2. Connection settings live in a stable config dir and are migrated once
     from the legacy workspace location, so agent updates never wipe them.
"""

from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


# --------------------------------------------------------------------------
# 1. Semantic update comparison
# --------------------------------------------------------------------------
from agent import updater  # noqa: E402


@pytest.mark.parametrize(
    "latest,current,expected",
    [
        ("2.19.0", "2.18.2", True),   # genuinely newer -> prompt
        ("2.18.2", "2.18.2", False),  # equal -> no prompt (label-only republish)
        ("2.18.0", "2.18.2", False),  # older manifest -> no prompt
        ("2.20.0", "2.19.0", True),
        ("2.9.0", "2.18.2", False),   # much older -> no prompt
        ("2.19.1", "2.19.0", True),   # patch bump -> prompt
    ],
)
def test_is_newer(latest: str, current: str, expected: bool) -> None:
    assert updater._is_newer(latest, current) is expected


def test_check_for_update_equal_version_not_available(monkeypatch) -> None:
    from agent.version import AGENT_VERSION

    monkeypatch.setattr(updater, "resolve_manifest_url", lambda: "http://x/m.json")
    monkeypatch.setattr(updater, "_fetch_manifest", lambda url: {"version": AGENT_VERSION})
    out = updater.check_for_update()
    assert out["update_available"] is False
    assert out["reachable"] is True


def test_check_for_update_newer_version_available(monkeypatch) -> None:
    monkeypatch.setattr(updater, "resolve_manifest_url", lambda: "http://x/m.json")
    monkeypatch.setattr(updater, "_fetch_manifest", lambda url: {"version": "99.0.0"})
    assert updater.check_for_update()["update_available"] is True


# --------------------------------------------------------------------------
# 2. Update-proof settings persistence + one-time migration
# --------------------------------------------------------------------------
def test_settings_use_stable_config_dir(monkeypatch, tmp_path) -> None:
    cfg = tmp_path / "cfg"
    ws = tmp_path / "ws"
    monkeypatch.setenv("TT_CONFIG_DIR", str(cfg))
    monkeypatch.setenv("TT_WORKSPACE_DIR", str(ws))
    import core.app_config as app_config

    importlib.reload(app_config)
    assert Path(app_config.SETTINGS_PATH) == cfg / "settings.json"
    # The config dir must NOT be inside the workspace (survives updates).
    assert str(ws) not in str(app_config.SETTINGS_PATH)


def test_legacy_settings_migrated_once(monkeypatch, tmp_path) -> None:
    cfg = tmp_path / "cfg"
    ws = tmp_path / "ws"
    ws.mkdir(parents=True, exist_ok=True)
    # Seed a legacy settings.json in the old workspace location.
    (ws / "settings.json").write_text(
        json.dumps({"organization": "acme", "project_prefix": "P_"}),
        encoding="utf-8",
    )
    monkeypatch.setenv("TT_CONFIG_DIR", str(cfg))
    monkeypatch.setenv("TT_WORKSPACE_DIR", str(ws))
    import core.app_config as app_config
    import core.settings_store as settings_store

    importlib.reload(app_config)
    importlib.reload(settings_store)

    # Reading a setting triggers the one-time migration into the stable dir.
    assert settings_store.get_setting("organization") == "acme"
    assert (cfg / "settings.json").exists()


@pytest.fixture(autouse=True)
def _restore_modules():
    """Reload the config-dependent modules back to their env-free defaults so
    reloads in these tests don't leak into other test files."""
    yield
    for name in ("core.app_config", "core.settings_store"):
        if name in sys.modules:
            os.environ.pop("TT_CONFIG_DIR", None)
            os.environ.pop("TT_WORKSPACE_DIR", None)
            importlib.reload(sys.modules[name])
