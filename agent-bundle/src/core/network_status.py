"""
network_status.py
Lightweight network health tracker. Reports API call outcomes and exposes
current status for the UI NW indicator.

ASCII-only; fully type-hinted.
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Final

_ONLINE_WINDOW: Final[float] = 30.0

_last_success: float = 0.0
_last_failure: float = 0.0


class NetworkStatus(Enum):
    ONLINE = "online"
    IDLE = "idle"
    OFFLINE = "offline"


def report_success() -> None:
    """Call after a successful API response (embedding or LLM)."""
    global _last_success
    _last_success = time.time()


def report_failure() -> None:
    """Call after a failed API attempt (timeout, connection error, auth)."""
    global _last_failure
    _last_failure = time.time()


def current_status() -> NetworkStatus:
    """Determine network health from recent call history."""
    if _last_failure > _last_success:
        return NetworkStatus.OFFLINE
    if _last_success > 0.0 and (time.time() - _last_success) <= _ONLINE_WINDOW:
        return NetworkStatus.ONLINE
    return NetworkStatus.IDLE
