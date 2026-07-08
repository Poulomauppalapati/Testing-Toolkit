# Deterministic business-logic tests for core/ modules.
from __future__ import annotations

import base64

import pytest


# --------------------------------------------------------------------------
# source_types: suffix round-trip
# --------------------------------------------------------------------------
def test_source_suffix_roundtrip():
    from core.source_types import (
        SourceType,
        append_source_suffix,
        strip_source_suffix,
    )

    for st in (SourceType.ADO, SourceType.JIRA):
        full = append_source_suffix("MyProj", st)
        bare, detected = strip_source_suffix(full)
        assert bare == "MyProj"
        assert detected == st

    # Unsuffixed name -> bare unchanged.
    bare, _ = strip_source_suffix("Plain")
    assert bare == "Plain"


def test_strip_suffix_explicit():
    from core.source_types import SourceType, strip_source_suffix

    assert strip_source_suffix("X - JIRA") == ("X", SourceType.JIRA)
    assert strip_source_suffix("X - ADO") == ("X", SourceType.ADO)


# --------------------------------------------------------------------------
# source_resolver: default behaviour
# --------------------------------------------------------------------------
def test_resolve_source_explicit_suffix_wins():
    from core.source_types import SourceType
    from core.source_resolver import resolve_source

    assert resolve_source("Proj - JIRA") is SourceType.JIRA
    assert resolve_source("Proj - ADO") is SourceType.ADO


def test_resolve_source_defaults_to_ado_when_nothing_configured(monkeypatch):
    import core.settings_store as ss
    from core.source_types import SourceType
    from core.source_resolver import resolve_source

    monkeypatch.setattr(ss, "is_jira_configured", lambda: False)
    monkeypatch.setattr(ss, "is_configured", lambda: False)
    assert resolve_source("Unsuffixed") is SourceType.ADO


def test_resolve_source_jira_only(monkeypatch):
    import core.settings_store as ss
    from core.source_types import SourceType
    from core.source_resolver import resolve_source

    monkeypatch.setattr(ss, "is_jira_configured", lambda: True)
    monkeypatch.setattr(ss, "is_configured", lambda: False)
    assert resolve_source("Unsuffixed") is SourceType.JIRA


# --------------------------------------------------------------------------
# app_config: env parser, _cfg precedence, name/worker helpers
# --------------------------------------------------------------------------
def test_parse_env_text_robust():
    import core.app_config as ac

    assert ac._parse_env_text("A=1\nB=two\n") == {"A": "1", "B": "two"}
    # comments + blanks + surrounding whitespace
    assert ac._parse_env_text("# c\n\nA=1\n  # x\nB = 2 \n") == {
        "A": "1", "B": "2"}
    # no '=' line is skipped
    assert "GARBAGE" not in ac._parse_env_text("GARBAGE LINE\nA=1\n")
    # '=' inside value preserved
    assert ac._parse_env_text("URL=http://x/y?a=b&c=d\n")["URL"] == \
        "http://x/y?a=b&c=d"
    # leading '=' (empty key) skipped
    assert ac._parse_env_text("=bad\nA=ok\n") == {"A": "ok"}
    # CRLF
    assert ac._parse_env_text("A=1\r\nB=2\r\n") == {"A": "1", "B": "2"}
    # empty input
    assert ac._parse_env_text("") == {}


def test_cfg_precedence(monkeypatch):
    import core.app_config as ac

    monkeypatch.setenv("ZZ_CFG_TEST", "fromenv")
    assert ac._cfg("ZZ_CFG_TEST", "def") == "fromenv"
    assert ac._cfg("DEFINITELY_MISSING_KEY", "def") == "def"


def test_display_project_name():
    from core.app_config import display_project_name

    assert display_project_name("PRE-Alpha", "PRE-") == "Alpha"
    # case-insensitive prefix
    assert display_project_name("pre-Beta", "PRE-") == "Beta"
    # no prefix match -> unchanged
    assert display_project_name("Gamma", "PRE-") == "Gamma"
    # stripping to empty falls back to full
    assert display_project_name("PRE-", "PRE-") == "PRE-"


def test_resolve_index_workers():
    from core.app_config import resolve_index_workers

    assert resolve_index_workers(0) == 1
    assert resolve_index_workers(-5) == 1
    assert resolve_index_workers(1) == 1
    assert resolve_index_workers(1000) >= 1


# --------------------------------------------------------------------------
# pat_store: encrypted-at-rest round-trip
# --------------------------------------------------------------------------
def test_pat_store_roundtrip(tmp_install):
    import importlib
    import core.pat_store as ps
    importlib.reload(ps)

    tok = "super-secret-pat-XYZ-123"
    assert ps.save_pat(tok) is True
    assert ps.load_pat() == tok

    # not stored in plaintext anywhere under the isolated dir
    leaked = False
    for p in tmp_install.rglob("*"):
        if p.is_file():
            try:
                if tok.encode() in p.read_bytes():
                    leaked = True
            except OSError:
                pass
    assert not leaked, "PAT stored in plaintext"

    assert ps.clear_pat() is True
    assert ps.load_pat() in (None, "")


def test_pat_store_empty():
    import core.pat_store as ps

    # empty save/load must not crash
    ps.save_pat("")
    assert ps.load_pat() in (None, "")


# --------------------------------------------------------------------------
# network_status: state machine
# --------------------------------------------------------------------------
def test_network_status_transitions():
    import core.network_status as ns

    ns.report_success()
    assert ns.current_status() == ns.NetworkStatus.ONLINE
    ns.report_failure()
    assert ns.current_status() == ns.NetworkStatus.OFFLINE
    ns.report_success()
    assert ns.current_status() == ns.NetworkStatus.ONLINE


# --------------------------------------------------------------------------
# model_router: routing is total over all tasks
# --------------------------------------------------------------------------
def test_model_router_total():
    from core.model_router import Task, route, tier_for_task

    for task in Task:
        model = route(task)
        assert isinstance(model, str) and model
        assert tier_for_task(task) is not None


# --------------------------------------------------------------------------
# http_retry: ssl exception discovery never crashes
# --------------------------------------------------------------------------
def test_ssl_exception_types():
    from core.http_retry import ssl_exception_types

    types = ssl_exception_types()
    assert isinstance(types, tuple)
    assert all(isinstance(t, type) for t in types)
