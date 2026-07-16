"""
middleware_trace.py
FastAPI middleware: Dynatrace-level request/response tracing.

Captures:
- Request entry with method, path, query, headers, client IP
- Response exit with status code and duration
- Full correlation context (trace_id, span_id, session_id)
- Slow request flagging (>2s at DEBUG, >5s at WARNING)
- Request body size tracking
- Error response stack capture
"""
from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from core.trace import (
    TRACE,
    TraceContext,
    _json_entry,
    trace_dependency,
)
from core.app_logging import get_logger

_logger = get_logger("http")


class TraceRequestMiddleware(BaseHTTPMiddleware):
    """Full-depth request lifecycle tracing with correlation context."""

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        req_id = uuid.uuid4().hex[:12]
        method = request.method
        path = request.url.path
        client = request.client.host if request.client else "unknown"

        # Extract or generate correlation IDs
        incoming_trace = request.headers.get("x-trace-id", "")
        session_id = request.headers.get("x-session-id", "")

        # Start trace context for the request lifecycle
        ctx = TraceContext.start(
            session_id=session_id,
            parent_trace_id=incoming_trace,
        )

        content_length = request.headers.get("content-length", "0")
        user_agent = request.headers.get("user-agent", "")[:100]

        _logger.log(TRACE, _json_entry(
            "TRACE", "request_start", "http.server", f"{method} {path}",
            user_context=client,
            metadata={
                "req_id": req_id,
                "query": str(request.url.query),
                "content_length": content_length,
                "user_agent": user_agent,
                "trace_id": ctx.trace_id,
                "span_id": ctx.span_id,
            },
        ))

        t0 = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
            _logger.log(TRACE, _json_entry(
                "TRACE", "request_error", "http.server", f"{method} {path}",
                user_context=client,
                duration_ms=elapsed_ms,
                metadata={
                    "req_id": req_id,
                    "error_type": type(exc).__name__,
                    "error_msg": str(exc)[:500],
                },
            ))
            ctx.end()
            raise

        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)

        _logger.log(TRACE, _json_entry(
            "TRACE", "request_end", "http.server", f"{method} {path}",
            user_context=client,
            duration_ms=elapsed_ms,
            metadata={
                "req_id": req_id,
                "status": response.status_code,
                "trace_id": ctx.trace_id,
            },
        ))

        # Surface slow requests in the human-readable log
        if elapsed_ms > 5000:
            _logger.warning(
                "[SLOW] %s %s took %.0fms (status %d)",
                method, path, elapsed_ms, response.status_code,
            )
        elif elapsed_ms > 2000:
            _logger.debug(
                "[SLOW] %s %s took %.0fms (status %d)",
                method, path, elapsed_ms, response.status_code,
            )

        # Inject trace headers into response for frontend correlation
        response.headers["x-trace-id"] = ctx.trace_id
        response.headers["x-duration-ms"] = str(elapsed_ms)

        ctx.end()
        return response
