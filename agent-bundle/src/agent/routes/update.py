"""Agent update endpoints.

Detection: compare running version with the published manifest.
Patch apply: for patch-level updates only, download source overlay files from
the manifest and replace in-place. Minor/major updates still require reinstall.
"""

from __future__ import annotations

import sys

from fastapi import APIRouter

from agent import updater
from core.trace import trace

router = APIRouter()


@router.get("/status")
@trace
async def update_status() -> dict:
    """Return current vs. available version without mutating the installation."""
    return updater.check_for_update()


@router.post("/apply")
@trace
async def apply_patch() -> dict:
    """Apply a patch-level update via source overlay. Refuses non-patch updates.
    After success the agent process should be restarted for changes to take effect."""
    result = updater.apply_patch()
    if result.get("ok") and result.get("restart_required"):
        # Schedule a graceful restart after responding to the client.
        import asyncio
        import os
        import signal

        async def _restart() -> None:
            await asyncio.sleep(1.0)
            os.kill(os.getpid(), signal.SIGTERM)

        asyncio.get_event_loop().create_task(_restart())
    return result


@router.get("/revert/status")
@trace
async def revert_status() -> dict:
    """Check if a revert snapshot is available from a prior patch."""
    return updater.revert_info()


@router.post("/revert")
@trace
async def revert_release() -> dict:
    """Revert the last applied patch, restoring the previous version."""
    result = updater.revert_patch()
    if result.get("ok") and result.get("restart_required"):
        import asyncio
        import os
        import signal

        async def _restart() -> None:
            await asyncio.sleep(1.0)
            os.kill(os.getpid(), signal.SIGTERM)

        asyncio.get_event_loop().create_task(_restart())
    return result
