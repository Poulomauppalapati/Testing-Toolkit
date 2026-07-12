"""Non-destructive agent version detection.

The agent reads the install-time update configuration and compares its running
version with the published manifest. It deliberately cannot download files,
install dependencies, patch source, or restart the process. New versions are
installed through the normal installer so settings and project data remain
under the installer's preservation contract.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx

from agent.version import AGENT_VERSION

DEFAULT_REPO = "nrcharanvignesh/Testing-Toolkit"
DEFAULT_REF = "parts"


def install_dir() -> Path:
    """Directory holding the agent's install-time update configuration."""
    return Path(
        os.environ.get("TT_INSTALL_DIR", Path.home() / "TestingToolkitWeb")
    ).expanduser()


def _config_path() -> Path:
    return install_dir() / "update.json"


def _load_config() -> dict[str, Any]:
    try:
        data = json.loads(_config_path().read_text())
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _manifest_url_for(repo: str, ref: str) -> str:
    repo = (repo or DEFAULT_REPO).strip()
    ref = (ref or DEFAULT_REF).strip()
    return f"https://api.github.com/repos/{repo}/contents/agent-update.json?ref={ref}"


def resolve_manifest_url() -> str:
    """Resolve the manifest URL without changing the installation."""
    config = _load_config()
    explicit = str(
        config.get("manifest_url", "")
        or os.environ.get("AGENT_MANIFEST_URL", "")
    ).strip()
    if explicit:
        return explicit

    token = str(
        config.get("token", "") or os.environ.get("TT_UPDATE_TOKEN", "")
    ).strip()
    if not token:
        return ""
    return _manifest_url_for(
        str(config.get("repo", "") or os.environ.get("TT_UPDATE_REPO", "")),
        str(config.get("ref", "") or os.environ.get("TT_UPDATE_REF", "")),
    )


def _auth_headers() -> dict[str, str]:
    config = _load_config()
    token = str(
        config.get("token", "") or os.environ.get("TT_UPDATE_TOKEN", "")
    ).strip()
    headers = {
        "Accept": "application/vnd.github.raw",
        "User-Agent": "TestingToolkit-Agent",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _fetch_manifest(url: str) -> dict[str, Any] | None:
    try:
        response = httpx.get(
            url,
            headers=_auth_headers(),
            timeout=10,
            follow_redirects=True,
        )
        if response.status_code != 200:
            return None
        data = response.json()
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _version_tuple(v: str) -> tuple[int, ...]:
    parts: list[int] = []
    for chunk in str(v).strip().split("."):
        try:
            parts.append(int(chunk))
        except ValueError:
            parts.append(0)
    return tuple(parts) or (0,)


def _is_newer(latest: str, current: str) -> bool:
    """True only when ``latest`` is STRICTLY greater than ``current``.

    Using a semantic comparison (not ``!=``) means republishing a manifest at
    an equal or older version never prompts a reinstall. Web/UI-only releases
    deploy through Vercel and deliberately do not republish the manifest, so
    installed agents are never nagged to reinstall for a label change.
    """
    a, b = _version_tuple(latest), _version_tuple(current)
    n = max(len(a), len(b))
    a += (0,) * (n - len(a))
    b += (0,) * (n - len(b))
    return a > b


def check_for_update() -> dict[str, Any]:
    """Report current vs. available version without mutating the installation."""
    manifest_url = resolve_manifest_url()
    manifest = _fetch_manifest(manifest_url) if manifest_url else None
    latest = str(manifest.get("version", "")).strip() if manifest else ""
    return {
        "current": AGENT_VERSION,
        "latest": latest or None,
        "update_available": bool(latest and _is_newer(latest, AGENT_VERSION)),
        "configured": bool(manifest_url),
        "reachable": manifest is not None,
        "install_dir": str(install_dir()),
    }
