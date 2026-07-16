"""Tests for core.process_metrics — platform-native resource metrics."""
from __future__ import annotations

import time

from core.process_metrics import (
    _get_cpu_percent,
    _get_disk_usage_mb,
    _get_gpu_info,
    _get_memory_mb,
    _NUM_CPUS,
    _refresh_disk_async,
)


def test_get_memory_mb_returns_positive() -> None:
    mem = _get_memory_mb()
    assert isinstance(mem, float)
    assert mem > 0


def test_get_cpu_percent_returns_bounded() -> None:
    # First call primes the delta; second call gives a real reading
    _get_cpu_percent()
    time.sleep(0.05)
    pct = _get_cpu_percent()
    assert isinstance(pct, float)
    assert 0 <= pct <= 100


def test_num_cpus_positive() -> None:
    assert _NUM_CPUS >= 1


def test_get_disk_usage_mb_non_negative() -> None:
    usage = _get_disk_usage_mb()
    assert isinstance(usage, float)
    assert usage >= 0


def test_get_gpu_info_returns_string() -> None:
    info = _get_gpu_info()
    assert isinstance(info, str)


def test_get_gpu_info_cached() -> None:
    a = _get_gpu_info()
    b = _get_gpu_info()
    assert a is b


def test_refresh_disk_async_does_not_block() -> None:
    start = time.monotonic()
    _refresh_disk_async()
    elapsed = time.monotonic() - start
    # Should return immediately (thread spawns in background)
    assert elapsed < 1.0
