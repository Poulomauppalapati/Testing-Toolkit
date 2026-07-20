"""
automation/artifact_collector.py
Manages artifact output directory structure and collection.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)


def _safe_filename(title: str) -> str:
    """Convert a test case title into a filesystem-safe filename."""
    safe = re.sub(r"[^\w\s\-]", "", title)
    safe = re.sub(r"\s+", "_", safe.strip())
    return safe[:80] or "recording"


def _remux_to_mkv(webm_path: Path, mkv_path: Path) -> bool:
    """Remux a WebM file to MKV using ffmpeg (lossless copy)."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False
    try:
        subprocess.run(
            [ffmpeg, "-y", "-i", str(webm_path), "-c", "copy", str(mkv_path)],
            capture_output=True, timeout=60,
        )
        if mkv_path.exists() and mkv_path.stat().st_size > 0:
            webm_path.unlink(missing_ok=True)
            return True
    except Exception as exc:
        _log.debug("ffmpeg remux failed: %s", exc)
    return False


class ArtifactCollector:
    """Creates and manages artifact directory structure for a test case.

    Structure:
        output_dir/{tc_id}/screenshots/
        output_dir/{tc_id}/video/
        output_dir/{tc_id}/scripts/
    """

    def __init__(self, output_dir: Path, tc_id: str, title: str = "") -> None:
        self._base = output_dir / tc_id
        self._screenshot_dir = self._base / "screenshots"
        self._video_dir = self._base / "video"
        self._script_dir = self._base / "scripts"
        self._title = title
        self._tc_id = tc_id

        # Create all dirs upfront
        self._screenshot_dir.mkdir(parents=True, exist_ok=True)
        self._video_dir.mkdir(parents=True, exist_ok=True)
        self._script_dir.mkdir(parents=True, exist_ok=True)

    @property
    def base_dir(self) -> Path:
        return self._base

    @property
    def screenshot_dir(self) -> Path:
        return self._screenshot_dir

    @property
    def video_dir(self) -> Path:
        return self._video_dir

    @property
    def script_dir(self) -> Path:
        return self._script_dir

    def collect_video(self) -> Path | None:
        """Find video, rename to title-based name, and convert to MKV.

        Playwright saves videos as .webm with UUID filenames. This method
        renames to a human-readable title and attempts MKV remux via ffmpeg.
        Falls back to renamed .webm if ffmpeg is unavailable.
        """
        video_files = list(self._video_dir.glob("*.webm"))
        mkv_files = list(self._video_dir.glob("*.mkv"))
        if mkv_files:
            return mkv_files[0]
        if not video_files:
            return None

        source = video_files[0]
        base_name = _safe_filename(self._title) if self._title else self._tc_id
        mkv_dest = self._video_dir / f"{base_name}.mkv"
        if _remux_to_mkv(source, mkv_dest):
            return mkv_dest
        # Fallback: rename webm with proper title
        renamed = self._video_dir / f"{base_name}.webm"
        if renamed != source:
            source.rename(renamed)
        return renamed

    def save_script(self, script_content: str, tc_id: str) -> Path:
        """Write a generated script to the scripts directory.

        Args:
            script_content: Python script source.
            tc_id: Test case ID (used in filename).

        Returns:
            Path to the written script file.
        """
        filename = f"{tc_id}_replay.py"
        path = self._script_dir / filename
        path.write_text(script_content, encoding="utf-8")
        return path

    def list_screenshots(self) -> list[Path]:
        """Return all screenshot files sorted by name."""
        files = list(self._screenshot_dir.glob("*.png"))
        return sorted(files)

    def manifest(self) -> dict[str, Any]:
        """Return a manifest dict summarizing collected artifacts.

        Keys: screenshots (list of paths), video (path or None),
              scripts (list of paths), base_dir.
        """
        screenshots = self.list_screenshots()
        video = self.collect_video()
        scripts = sorted(self._script_dir.glob("*.py"))

        return {
            "base_dir": str(self._base),
            "screenshots": [str(p) for p in screenshots],
            "video": str(video) if video else None,
            "scripts": [str(p) for p in scripts],
            "screenshot_count": len(screenshots),
            "has_video": video is not None,
            "script_count": len(scripts),
        }
