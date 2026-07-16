"""
events.py
POST /events/batch - receives batched user-action events from the frontend.
Each event is logged at TRACE level as structured JSON.
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from core.trace import TRACE, _json_entry
from core.app_logging import get_logger

router = APIRouter()
_logger = get_logger("user_events")


class UserEvent(BaseModel):
    event_type: str
    source: str
    action: str
    user_context: str = ""
    duration_ms: float | None = None
    metadata: dict = {}
    client_ts: float = 0


class EventBatch(BaseModel):
    events: list[UserEvent]


@router.post("/batch")
async def receive_events(batch: EventBatch) -> dict[str, int]:
    """Ingest a batch of frontend user-action events."""
    for evt in batch.events:
        _logger.log(TRACE, _json_entry(
            "TRACE",
            evt.event_type,
            evt.source,
            evt.action,
            user_context=evt.user_context,
            duration_ms=evt.duration_ms,
            metadata={**evt.metadata, "client_ts": evt.client_ts},
        ))
    return {"accepted": len(batch.events)}
