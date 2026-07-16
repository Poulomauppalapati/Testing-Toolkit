"""Tests for core.model_router — task-based model selection."""
from __future__ import annotations

from core.model_router import (
    Task,
    Tier,
    model_for_tier,
    route,
    tier_for_task,
    _TASK_TIER,
)


def test_all_tasks_have_tier_mapping() -> None:
    for task in Task:
        assert task in _TASK_TIER, f"{task} missing from _TASK_TIER"


def test_model_for_tier_returns_strings() -> None:
    for tier in Tier:
        model = model_for_tier(tier)
        assert isinstance(model, str)
        assert len(model) > 0


def test_route_returns_nonempty_string_for_all_tasks() -> None:
    for task in Task:
        model = route(task)
        assert isinstance(model, str)
        assert len(model) > 0


def test_tier_for_task_returns_tier_enum() -> None:
    for task in Task:
        tier = tier_for_task(task)
        assert isinstance(tier, Tier)


def test_frontier_tasks_use_large_model() -> None:
    from core.app_config import MODEL_LARGE

    frontier_tasks = [
        Task.GENERATE_TEST_CASES,
        Task.VERIFY_COVERAGE,
        Task.TEMPLATE_ANALYSIS,
        Task.DECOMPOSE_REQUIREMENTS,
    ]
    for task in frontier_tasks:
        assert tier_for_task(task) == Tier.FRONTIER
        # Unless overridden, should resolve to MODEL_LARGE
        model = model_for_tier(Tier.FRONTIER)
        assert model == MODEL_LARGE


def test_small_tasks_use_small_model() -> None:
    from core.app_config import MODEL_SMALL

    small_tasks = [Task.CONTEXTUALIZE_CHUNK, Task.LLM_RERANK]
    for task in small_tasks:
        assert tier_for_task(task) == Tier.SMALL
        model = model_for_tier(Tier.SMALL)
        assert model == MODEL_SMALL
