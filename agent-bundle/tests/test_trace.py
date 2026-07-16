"""Tests for core.trace -- TRACE level, @trace decorator, TraceContext."""
from __future__ import annotations

import asyncio
import json
import logging
from unittest.mock import patch

import pytest

from core.trace import (
    TRACE,
    TraceContext,
    _json_entry,
    current_session_id,
    current_span_id,
    current_trace_id,
    trace,
    trace_custom_event,
    trace_dependency,
    trace_state_change,
    trace_user_action,
)


def test_trace_level_value() -> None:
    assert TRACE == 5
    assert logging.getLevelName(5) == "TRACE"


def test_json_entry_minimal() -> None:
    line = _json_entry("TRACE", "test_event", "test_source", "test_action")
    parsed = json.loads(line)
    assert parsed["level"] == "TRACE"
    assert parsed["event_type"] == "test_event"
    assert parsed["source"] == "test_source"
    assert parsed["action"] == "test_action"
    assert "ts" in parsed
    assert "pid" in parsed


def test_json_entry_with_metadata() -> None:
    line = _json_entry(
        "TRACE", "ev", "src", "act",
        user_context="user1",
        duration_ms=42.5,
        metadata={"key": "val"},
    )
    parsed = json.loads(line)
    assert parsed["user_context"] == "user1"
    assert parsed["duration_ms"] == 42.5
    assert parsed["meta"]["key"] == "val"


def test_json_entry_omits_empty_fields() -> None:
    line = _json_entry("TRACE", "ev", "src", "act")
    parsed = json.loads(line)
    assert "user_context" not in parsed
    assert "duration_ms" not in parsed
    assert "meta" not in parsed
    assert "stack" not in parsed


class TestTraceContext:
    def test_start_and_end(self) -> None:
        ctx = TraceContext.start(session_id="sess-1", user_id="usr-1")
        assert current_session_id() == "sess-1"
        assert current_trace_id() == ctx.trace_id
        assert current_span_id() == ctx.span_id
        ctx.end()
        assert current_session_id() == ""
        assert current_trace_id() == ""

    def test_child_span_inherits_trace_id(self) -> None:
        ctx = TraceContext.start()
        child = ctx.child_span()
        assert child.trace_id == ctx.trace_id
        assert child.parent_span_id == ctx.span_id
        assert child.span_id != ctx.span_id
        ctx.end()

    def test_elapsed_ms(self) -> None:
        ctx = TraceContext.start()
        import time
        time.sleep(0.01)
        assert ctx.elapsed_ms() >= 5
        ctx.end()


class TestTraceDecorator:
    def test_sync_function(self) -> None:
        @trace
        def add(a: int, b: int) -> int:
            return a + b

        assert add(2, 3) == 5

    def test_sync_exception_propagates(self) -> None:
        @trace
        def fail() -> None:
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            fail()

    def test_async_function(self) -> None:
        @trace
        async def async_add(a: int, b: int) -> int:
            return a + b

        result = asyncio.run(async_add(4, 5))
        assert result == 9

    def test_async_exception_propagates(self) -> None:
        @trace
        async def async_fail() -> None:
            raise RuntimeError("async boom")

        with pytest.raises(RuntimeError, match="async boom"):
            asyncio.run(async_fail())

    def test_preserves_function_name(self) -> None:
        @trace
        def my_func() -> None:
            pass

        assert my_func.__name__ == "my_func"

    def test_preserves_async_function_name(self) -> None:
        @trace
        async def my_async_func() -> None:
            pass

        assert my_async_func.__name__ == "my_async_func"


class TestTracingHelpers:
    def test_trace_dependency(self) -> None:
        # Should not raise
        trace_dependency(
            "http", "https://example.com/api", "GET 200",
            duration_ms=50.0, success=True, status_code=200,
        )

    def test_trace_custom_event(self) -> None:
        trace_custom_event("config_loaded", "app_config", metadata={"key": "val"})

    def test_trace_user_action(self) -> None:
        trace_user_action(
            "click:generate", "GenerateDialog",
            user_context="project-a", duration_ms=10.0,
        )

    def test_trace_state_change(self) -> None:
        trace_state_change("theme", "light", "dark", "settings")
