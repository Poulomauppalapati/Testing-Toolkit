# Test harness bootstrap. Isolates all config/state under a temp dir so tests
# never touch a real user profile, and forces fast-failing network settings.
from __future__ import annotations

import os
import socket
import sys
import tempfile
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# Isolate install/config/home to a throwaway dir BEFORE any module loads.
_TMP = tempfile.mkdtemp(prefix="tt-test-")
os.environ["TT_INSTALL_DIR"] = _TMP
os.environ["HOME"] = _TMP
os.environ["XDG_CONFIG_HOME"] = _TMP
os.environ["TT_SKIP_MODEL_PRELOAD"] = "1"
# Point network at a dead port so any accidental real call fails fast.
os.environ["BASE_URL"] = "http://127.0.0.1:9/v1"
os.environ["API_KEY"] = ""
os.environ["HTTP_TIMEOUT_SEC"] = "3"
os.environ["DOWNLOAD_TIMEOUT_SEC"] = "3"
socket.setdefaulttimeout(6)


@pytest.fixture()
def tmp_install(tmp_path, monkeypatch):
    """Per-test isolated install dir for tests that write config/state."""
    monkeypatch.setenv("TT_INSTALL_DIR", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    return tmp_path
