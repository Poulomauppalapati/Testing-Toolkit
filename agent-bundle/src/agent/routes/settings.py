"""Settings endpoints — read/write local settings and secrets."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class SettingsResponse(BaseModel):
    configured: bool
    has_api_key: bool
    has_pat: bool
    organization: str
    model: str
    fast_model: str
    fallback_model: str
    base_url: str
    project_prefix: str
    tour_completed: bool
    # -- JIRA source (secondary work-item source) --
    jira_configured: bool = False
    has_jira_pat: bool = False
    jira_url: str = ""
    jira_user: str = ""
    jira_project_prefix: str = ""


class SaveSettingsRequest(BaseModel):
    organization: str | None = None
    base_url: str | None = None
    model: str | None = None
    fast_model: str | None = None
    fallback_model: str | None = None
    project_prefix: str | None = None
    api_key: str | None = None
    pat: str | None = None
    # -- JIRA source --
    jira_url: str | None = None
    jira_user: str | None = None
    jira_pat: str | None = None
    jira_project_prefix: str | None = None


@router.get("", response_model=SettingsResponse)
async def get_settings() -> SettingsResponse:
    from core.settings_store import (
        get_setting,
        get_tour_completed,
        has_api_key,
        is_configured,
        is_jira_configured,
        load_jira_pat,
        load_pat_value,
        KEY_BASE_URL,
        KEY_FALLBACK_MODEL,
        KEY_FAST_MODEL,
        KEY_MODEL,
        KEY_ORG,
        KEY_PREFIX,
        KEY_JIRA_URL,
        KEY_JIRA_USER,
        KEY_JIRA_PREFIX,
    )
    return SettingsResponse(
        configured=is_configured(),
        has_api_key=has_api_key(),
        has_pat=bool(load_pat_value()),
        organization=get_setting(KEY_ORG),
        model=get_setting(KEY_MODEL),
        fast_model=get_setting(KEY_FAST_MODEL),
        fallback_model=get_setting(KEY_FALLBACK_MODEL),
        base_url=get_setting(KEY_BASE_URL),
        project_prefix=get_setting(KEY_PREFIX),
        tour_completed=get_tour_completed(),
        jira_configured=is_jira_configured(),
        has_jira_pat=bool(load_jira_pat()),
        jira_url=get_setting(KEY_JIRA_URL),
        jira_user=get_setting(KEY_JIRA_USER),
        jira_project_prefix=get_setting(KEY_JIRA_PREFIX),
    )


@router.post("")
async def save_settings(req: SaveSettingsRequest) -> dict:
    from core.settings_store import (
        save_api_key,
        save_pat_value,
        save_jira_pat,
        save_settings as save_plain,
        KEY_BASE_URL,
        KEY_FALLBACK_MODEL,
        KEY_FAST_MODEL,
        KEY_MODEL,
        KEY_ORG,
        KEY_PREFIX,
        KEY_JIRA_URL,
        KEY_JIRA_USER,
        KEY_JIRA_PREFIX,
    )

    plain: dict[str, str] = {}
    if req.organization is not None:
        plain[KEY_ORG] = req.organization
    if req.base_url is not None:
        plain[KEY_BASE_URL] = req.base_url
    if req.model is not None:
        plain[KEY_MODEL] = req.model
    if req.fast_model is not None:
        plain[KEY_FAST_MODEL] = req.fast_model
    if req.fallback_model is not None:
        plain[KEY_FALLBACK_MODEL] = req.fallback_model
    if req.project_prefix is not None:
        plain[KEY_PREFIX] = req.project_prefix
    if req.jira_url is not None:
        plain[KEY_JIRA_URL] = req.jira_url.strip()
    if req.jira_user is not None:
        plain[KEY_JIRA_USER] = req.jira_user.strip()
    if req.jira_project_prefix is not None:
        plain[KEY_JIRA_PREFIX] = req.jira_project_prefix

    if plain:
        save_plain(plain)

    if req.api_key:
        if not save_api_key(req.api_key):
            raise HTTPException(500, "Failed to save API key")

    if req.pat:
        if not save_pat_value(req.pat):
            raise HTTPException(500, "Failed to save PAT")

    if req.jira_pat:
        if not save_jira_pat(req.jira_pat):
            raise HTTPException(500, "Failed to save JIRA token")

    return {"ok": True}


class TourRequest(BaseModel):
    completed: bool = True


@router.post("/tour")
async def set_tour(req: TourRequest) -> dict:
    """Persist whether the first-run guided tour has been completed/skipped, so
    it does not reappear on refresh even if the browser localStorage is wiped."""
    from core.settings_store import set_tour_completed

    set_tour_completed(req.completed)
    return {"ok": True, "tour_completed": req.completed}


# ---------------------------------------------------------------------------
# Per-project system prompts (mirrors ProjectKbDialog's System prompt section)
# ---------------------------------------------------------------------------
class SystemPromptResponse(BaseModel):
    project: str
    scope: str          # "" = General/default, else implementation|sit|uat
    text: str


class SaveSystemPromptRequest(BaseModel):
    project: str
    scope: str = ""
    text: str


@router.get("/system-prompt", response_model=SystemPromptResponse)
async def get_system_prompt(project: str, scope: str = "") -> SystemPromptResponse:
    """Read the editable system prompt for a project + phase scope. An empty
    scope returns the General/manual default prompt."""
    import core.project_store as ps

    text = ps.read_system_prompt(project, scope or None)
    return SystemPromptResponse(project=project, scope=scope, text=text)


@router.post("/system-prompt", response_model=SystemPromptResponse)
async def save_system_prompt(req: SaveSystemPromptRequest) -> SystemPromptResponse:
    """Persist the system prompt for a project + phase scope. Mirrors
    ProjectKbDialog._save_prompt; an empty body is rejected like the desktop."""
    import core.project_store as ps

    text = (req.text or "").strip()
    if not text:
        raise HTTPException(
            400,
            "The system prompt cannot be empty. Use reset to restore the "
            "standard prompt.",
        )
    if not ps.write_system_prompt(req.project, text, req.scope or None):
        raise HTTPException(500, "Could not write the system prompt.")
    return SystemPromptResponse(project=req.project, scope=req.scope, text=text)


@router.post("/system-prompt/reset", response_model=SystemPromptResponse)
async def reset_system_prompt(req: SaveSystemPromptRequest) -> SystemPromptResponse:
    """Reset the system prompt for a project + phase scope to the standard
    default (mirrors ProjectKbDialog._reset_prompt)."""
    import core.project_store as ps

    ps.reset_system_prompt(req.project, req.scope or None)
    text = ps.read_system_prompt(req.project, req.scope or None)
    return SystemPromptResponse(project=req.project, scope=req.scope, text=text)
