# Deterministic tests for ADO/JIRA helpers, generation payload transforms,
# quality scoring, traceability, and diff logic.
from __future__ import annotations

import pytest


# --------------------------------------------------------------------------
# generation payload transforms
# --------------------------------------------------------------------------
def test_to_jira_payload_maps_parent_key():
    import agent.routes.generate as g

    payload = {
        "stories": [
            {"parent_work_item_id": "PROJ-1", "title": "Login",
             "test_cases": [{"action": "a", "expected": "e"}]},
            {"work_item_id": "PROJ-2", "title": "Logout", "test_cases": []},
        ]
    }
    out = g._to_jira_payload(payload)
    assert out["schema_version"] == 1
    assert out["stories"][0]["parent_key"] == "PROJ-1"
    assert out["stories"][0]["parent_title"] == "Login"
    assert len(out["stories"][0]["test_cases"]) == 1
    assert out["stories"][1]["parent_key"] == "PROJ-2"


def test_to_jira_payload_empty():
    import agent.routes.generate as g

    assert g._to_jira_payload({})["stories"] == []
    assert g._to_jira_payload({"stories": None})["stories"] == []


def test_regen_prompt_truncates_large_payload():
    import agent.routes.generate as g

    big = {"stories": [{"x": "y" * 100000}]}
    out = g._regen_system_prompt("BASE", "please fix", big)
    assert "BASE" in out
    assert "REGENERATION REQUEST" in out
    assert "please fix" in out
    assert "truncated" in out


def test_board_token_stable():
    import agent.routes.generate as g

    t1 = g._board_token("My Board")
    t2 = g._board_token("My Board")
    assert t1 == t2 and t1  # deterministic, non-empty


# --------------------------------------------------------------------------
# ADO extract helpers
# --------------------------------------------------------------------------
def test_html_to_text():
    from ado.extract import html_to_text

    assert html_to_text(None) == ""
    assert html_to_text("") == ""
    out = html_to_text("<p>Hello <b>world</b></p><ul><li>one</li><li>two</li></ul>")
    assert "Hello" in out and "world" in out
    assert "one" in out and "two" in out
    assert "<" not in out  # tags stripped


def test_extract_image_urls():
    from ado.extract import extract_image_urls

    assert extract_image_urls(None) == []
    html = '<img src="http://x/a.png"> text <img src="http://y/b.jpg">'
    urls = extract_image_urls(html)
    assert "http://x/a.png" in urls and "http://y/b.jpg" in urls


def test_safe_filename():
    from ado.extract import _safe_filename

    assert _safe_filename('a<b>c:d/e\\f|g?h*i') == "a_b_c_d_e_f_g_h_i"
    assert _safe_filename("") == "unnamed_attachment"
    assert _safe_filename("   ...   ") == "unnamed_attachment"
    # length cap
    assert len(_safe_filename("x" * 500)) <= 200


def test_build_auth_header():
    from ado.extract import build_auth_header

    h = build_auth_header("mypat")
    assert "Authorization" in h
    assert h["Authorization"].startswith("Basic ")


# --------------------------------------------------------------------------
# JIRA helpers
# --------------------------------------------------------------------------
def test_jql_escape():
    from jira.boards import _jql_escape

    assert _jql_escape("plain") == "plain"
    # single quote escaped
    assert _jql_escape("O'Brien") == "O\\'Brien"
    # backslash escaped first (no double-escape)
    assert _jql_escape("a\\b") == "a\\\\b"


def test_build_jira_dump_keyed_by_key():
    from jira.boards import build_jira_work_item_dump

    details = [
        {"key": "PROJ-10", "summary": "As a user I want X",
         "description": "details", "issue_type": "Story"},
    ]
    dump = build_jira_work_item_dump(details)
    assert "PROJ-10" in dump  # dump references the issue KEY


# --------------------------------------------------------------------------
# tc_types
# --------------------------------------------------------------------------
def test_tc_types():
    import testgen.tc_types as t

    assert t.is_valid("sit") and t.is_valid("uat") and t.is_valid("implementation")
    assert not t.is_valid("bogus")
    assert t.display_name("sit")
    assert t.button_label("uat")
    # default_prompt always returns the canonical contract
    for tt in t.TC_TYPES:
        p = t.default_prompt(tt)
        assert isinstance(p, str) and len(p) > 50


# --------------------------------------------------------------------------
# quality scorer
# --------------------------------------------------------------------------
def test_score_payload():
    from testgen.quality_scorer import score_payload

    payload = {
        "test_cases": [
            {"title": "Verify login on the login page",
             "steps": [
                 {"action": "Open the login page", "expected": "Login form shows"},
                 {"action": "Enter valid username in the username field",
                  "expected": "Username accepted"},
                 {"action": "Enter valid password", "expected": "Password masked"},
                 {"action": "Click the Sign In button", "expected": "Dashboard loads"},
             ]},
            {"title": "Empty", "steps": []},
        ]
    }
    q = score_payload(payload)
    assert len(q.scores) == 2
    assert 0 <= q.avg_score <= 100
    # the empty test case should score below threshold
    assert q.below_threshold >= 1


def test_score_payload_empty():
    from testgen.quality_scorer import score_payload

    q = score_payload({"test_cases": []})
    assert q.avg_score == 0.0
    assert q.scores == []


# --------------------------------------------------------------------------
# traceability
# --------------------------------------------------------------------------
def test_build_traceability():
    from testgen.traceability import build_traceability

    payload = {
        "stories": [
            {"parent_work_item_id": "WI-1", "title": "Story One",
             "test_cases": [{"title": "tc1"}, {"title": "tc2"}]},
            {"parent_work_item_id": "WI-2", "title": "Story Two",
             "test_cases": []},
        ]
    }
    matrix = build_traceability(payload)
    assert matrix is not None
    assert len(matrix.items) >= 2


# --------------------------------------------------------------------------
# diff engine
# --------------------------------------------------------------------------
def test_diff_payloads():
    from testgen.diff_engine import diff_payloads

    old = {"test_cases": [{"id": "1", "title": "A", "steps": []}]}
    new = {"test_cases": [
        {"id": "1", "title": "A changed", "steps": []},
        {"id": "2", "title": "B new", "steps": []},
    ]}
    d = diff_payloads(old, new)
    assert d is not None
