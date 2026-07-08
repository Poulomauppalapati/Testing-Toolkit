# Import every non-private module in src/. Catches module-level breakage:
# missing symbols, bad imports, syntax errors, and the is_ready()-class of
# latent AttributeErrors that only surface when a module is first loaded.
from __future__ import annotations

import importlib
import os
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parent.parent / "src"


def _all_modules() -> list[str]:
    mods: list[str] = []
    for root, _dirs, files in os.walk(_SRC):
        if "__pycache__" in root:
            continue
        for f in sorted(files):
            if not f.endswith(".py") or f.startswith("_") or f == "version.py":
                continue
            rel = os.path.relpath(os.path.join(root, f), _SRC)
            mods.append(rel[:-3].replace(os.sep, "."))
    return sorted(mods)


@pytest.mark.parametrize("module", _all_modules())
def test_module_imports(module: str) -> None:
    importlib.import_module(module)


def test_server_app_has_all_routers() -> None:
    """The real ASGI app must mount every router (regression guard: a bare
    import once appeared to expose only 4 routes; the served app has ~76)."""
    from fastapi.testclient import TestClient

    import agent.server as server

    with TestClient(server.app) as client:
        spec = client.get("/openapi.json").json()
        paths = spec["paths"]
    assert len(paths) >= 60, f"expected >=60 routes, got {len(paths)}"
    # A few representative paths from different routers must be present.
    for p in ("/health", "/settings", "/kb/retrieve", "/sources/boards",
              "/generate/start", "/chat/stream"):
        assert any(rp == p or rp.startswith(p) for rp in paths), f"missing {p}"
