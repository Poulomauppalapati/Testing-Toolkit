"""LLM proxy endpoints — calls Anthropic API using locally-stored key."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter()


class CompleteRequest(BaseModel):
    model: str | None = None
    system: str = ""
    user: str
    max_tokens: int = 4096
    temperature: float = 0.0
    thinking_budget: int | None = None
    stop_sequences: list[str] | None = None


class CompleteResponse(BaseModel):
    text: str
    stop_reason: str
    input_tokens: int
    output_tokens: int


@router.post("/complete", response_model=CompleteResponse)
async def complete(req: CompleteRequest) -> CompleteResponse:
    """Single-shot LLM completion via the locally-stored API key."""
    from core.settings_store import get_setting, load_api_key, KEY_BASE_URL, KEY_MODEL
    from core.anthropic_client import AnthropicClient
    from core.settings_store import build_runtime_config

    api_key = load_api_key()
    if not api_key:
        raise HTTPException(400, "No API key configured")

    base_url = get_setting(KEY_BASE_URL)
    model = req.model or get_setting(KEY_MODEL)

    cfg = build_runtime_config()
    client = AnthropicClient(
        api_key=api_key, base_url=base_url, ssl_verify=cfg.build_ssl()
    )
    try:
        result = await client.complete_async(
            model=model,
            system=req.system,
            user=req.user,
            max_tokens=req.max_tokens,
            temperature=req.temperature,
            thinking_budget=req.thinking_budget,
            stop_sequences=req.stop_sequences,
        )
    except Exception as e:
        raise HTTPException(502, f"LLM API error: {e!r}")

    return CompleteResponse(
        text=result.text,
        stop_reason=result.stop_reason,
        input_tokens=result.usage.input_tokens,
        output_tokens=result.usage.output_tokens,
    )


@router.get("/models")
async def list_models() -> list[dict[str, str]]:
    """List available/working models from the configured API, grouped by
    provider (mirrors the desktop ConnectionFields.fetch_models)."""
    from core.settings_store import get_setting, load_api_key, KEY_BASE_URL
    from core.anthropic_client import (
        AnthropicClient,
        group_models_by_provider,
    )
    from core.settings_store import build_runtime_config

    api_key = load_api_key()
    if not api_key:
        raise HTTPException(400, "No API key configured")

    base_url = get_setting(KEY_BASE_URL)
    # Use the app's TLS handling (combined CA bundle / truststore) so corporate
    # self-signed proxy chains (Zscaler etc.) verify correctly. Without this the
    # client falls back to plain certifi and raises CERTIFICATE_VERIFY_FAILED.
    cfg = build_runtime_config()
    client = AnthropicClient(
        api_key=api_key, base_url=base_url, ssl_verify=cfg.build_ssl()
    )
    try:
        models = await client.list_working_models_async()
    except Exception as e:
        raise HTTPException(502, f"Failed to list models: {e!r}")

    # Flatten into ordered [{id, provider, label}] so the web UI can render the
    # same grouped dropdown the desktop builds with group_models_by_provider().
    out: list[dict[str, str]] = []
    for provider, items in group_models_by_provider(models):
        for m in items:
            out.append({
                "id": m.id,
                "provider": provider,
                "label": getattr(m, "label", "") or m.id,
            })
    return out
