"""Tests for agent.routes.events -- user-action event ingestion."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from agent.routes.events import router
from fastapi import FastAPI

app = FastAPI()
app.include_router(router, prefix="/events")
client = TestClient(app)


def test_batch_accepts_events() -> None:
    resp = client.post("/events/batch", json={
        "events": [
            {
                "event_type": "user_action",
                "source": "TestDialog",
                "action": "click:submit",
                "user_context": "project-a",
                "duration_ms": 15.5,
                "metadata": {"count": 3},
                "client_ts": 1721000000000,
            },
            {
                "event_type": "state_change",
                "source": "AppState",
                "action": "select_board",
            },
        ]
    })
    assert resp.status_code == 200
    assert resp.json() == {"accepted": 2}


def test_batch_empty_list() -> None:
    resp = client.post("/events/batch", json={"events": []})
    assert resp.status_code == 200
    assert resp.json() == {"accepted": 0}


def test_batch_missing_required_fields() -> None:
    resp = client.post("/events/batch", json={
        "events": [{"event_type": "user_action"}]
    })
    assert resp.status_code == 422


def test_batch_invalid_body() -> None:
    resp = client.post("/events/batch", json={"not_events": []})
    assert resp.status_code == 422
