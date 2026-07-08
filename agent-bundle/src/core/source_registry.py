"""Registry that manages multiple project source backends.

Pattern: register factory callables, instantiate lazily. Thread-safe.
"""
from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from core.source_types import ProjectInfo, SourceConfig, SourceType, append_source_suffix


class SourceRegistry:
    """Central registry for project source backends."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._factories: dict[SourceType, Callable[..., Any]] = {}
        self._configs: dict[SourceType, SourceConfig] = {}
        self._projects: dict[SourceType, list[str]] = {}

    def register(self, source_type: SourceType, factory: Callable[..., Any]) -> None:
        """Register a factory callable for a source type."""
        with self._lock:
            self._factories[source_type] = factory

    def get(self, source_type: SourceType) -> Any | None:
        """Return the registered factory/instance, or None."""
        with self._lock:
            return self._factories.get(source_type)

    def set_config(self, source_type: SourceType, config: SourceConfig) -> None:
        """Store connection config for a source type."""
        with self._lock:
            self._configs[source_type] = config

    def is_configured(self, source_type: SourceType) -> bool:
        """Check if this source has valid config (url + pat present)."""
        with self._lock:
            cfg = self._configs.get(source_type)
            if cfg is None:
                return False
            return bool(cfg.url and cfg.pat)

    def configured_sources(self) -> list[SourceType]:
        """Return list of sources that have valid config."""
        with self._lock:
            return [st for st in self._configs if self.is_configured(st)]

    def set_projects(self, source_type: SourceType, projects: list[str]) -> None:
        """Cache project names for a source."""
        with self._lock:
            self._projects[source_type] = list(projects)

    def clear_projects(self, source_type: SourceType) -> None:
        """Clear cached projects for a source."""
        with self._lock:
            self._projects.pop(source_type, None)

    def all_projects(self) -> list[ProjectInfo]:
        """Merge cached projects from all configured sources.

        Does NOT perform I/O -- only returns previously cached data.
        """
        with self._lock:
            result: list[ProjectInfo] = []
            for source_type, names in self._projects.items():
                for name in names:
                    result.append(
                        ProjectInfo(
                            name=name,
                            source_type=source_type,
                            display_name=append_source_suffix(name, source_type),
                        )
                    )
            return result


# ------------------------------------------------------------------
# Module-level singleton + public accessors
# ------------------------------------------------------------------

_registry = SourceRegistry()


def register_source(source_type: SourceType, factory: Callable[..., Any]) -> None:
    """Register a factory callable for a source type."""
    _registry.register(source_type, factory)


def get_source(source_type: SourceType) -> Any | None:
    """Return the registered factory/instance, or None."""
    return _registry.get(source_type)


def set_source_config(source_type: SourceType, config: SourceConfig) -> None:
    """Store connection config for a source type."""
    _registry.set_config(source_type, config)


def is_source_configured(source_type: SourceType) -> bool:
    """Check if this source has valid config."""
    return _registry.is_configured(source_type)


def configured_sources() -> list[SourceType]:
    """Return list of sources that have valid config."""
    return _registry.configured_sources()


def set_projects(source_type: SourceType, projects: list[str]) -> None:
    """Cache project names for a source."""
    _registry.set_projects(source_type, projects)


def clear_projects(source_type: SourceType) -> None:
    """Clear cached projects for a source."""
    _registry.clear_projects(source_type)


def all_projects() -> list[ProjectInfo]:
    """Merge cached projects from all configured sources."""
    return _registry.all_projects()
