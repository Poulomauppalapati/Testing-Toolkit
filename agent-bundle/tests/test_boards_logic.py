"""Unit tests for pure/sync logic in ado.boards.

Exercises ONLY the non-async, non-HTTP functions -- the deterministic
data-manipulation layer. Uses fake ADO-shaped data throughout; no live
network calls.
"""
from __future__ import annotations

from typing import Any

import pytest

from ado.boards import (
    BoardColumn,
    WorkItemRow,
    _build_wiql,
    _classify_relations,
    _count_tested_by,
    _is_link_relation,
    _is_test_relation,
    _norm,
    _parse_relations,
    _parse_row,
    _rel_target_id,
    _safe_name,
    _tally_test_counts,
    _wiql_escape,
    _wit_types_from_columns,
    group_rows_by_column,
)


# ------------------------------------------------------------------
# _wiql_escape
# ------------------------------------------------------------------
class TestWiqlEscape:
    def test_no_quotes(self) -> None:
        assert _wiql_escape("simple") == "simple"

    def test_single_quote_doubled(self) -> None:
        assert _wiql_escape("it's") == "it''s"

    def test_multiple_quotes(self) -> None:
        assert _wiql_escape("a'b'c") == "a''b''c"

    def test_empty_string(self) -> None:
        assert _wiql_escape("") == ""

    def test_only_quotes(self) -> None:
        assert _wiql_escape("'''") == "''''''"


# ------------------------------------------------------------------
# _norm
# ------------------------------------------------------------------
class TestNorm:
    def test_lowercase_strip_nonalnum(self) -> None:
        assert _norm("Tested By") == "testedby"

    def test_with_dots_hyphens(self) -> None:
        assert _norm("Microsoft.VSTS.Common.TestedBy-Forward") == "microsoftvstscommontestedbyforward"

    def test_empty(self) -> None:
        assert _norm("") == ""

    def test_none(self) -> None:
        assert _norm(None) == ""

    def test_numbers_preserved(self) -> None:
        assert _norm("Test123") == "test123"


# ------------------------------------------------------------------
# _wit_types_from_columns
# ------------------------------------------------------------------
class TestWitTypesFromColumns:
    def test_extracts_types_from_state_mappings(self) -> None:
        cols = [
            BoardColumn(id="1", name="New", column_type="incoming",
                        state_mappings={"Bug": "New", "User Story": "New"}),
            BoardColumn(id="2", name="Active", column_type="inProgress",
                        state_mappings={"Bug": "Active", "Task": "Active"}),
        ]
        result = _wit_types_from_columns(cols)
        assert sorted(result) == ["Bug", "Task", "User Story"]

    def test_empty_mappings_returns_defaults(self) -> None:
        cols = [
            BoardColumn(id="1", name="New", column_type="incoming",
                        state_mappings={}),
        ]
        result = _wit_types_from_columns(cols)
        # Should return _DEFAULT_WIT_TYPES
        assert "Epic" in result
        assert "Bug" in result

    def test_no_columns_returns_defaults(self) -> None:
        result = _wit_types_from_columns([])
        assert len(result) > 0
        assert "User Story" in result

    def test_deduplicates_across_columns(self) -> None:
        cols = [
            BoardColumn(id="1", name="A", column_type="incoming",
                        state_mappings={"Bug": "New"}),
            BoardColumn(id="2", name="B", column_type="incoming",
                        state_mappings={"Bug": "Active"}),
        ]
        result = _wit_types_from_columns(cols)
        assert result == ["Bug"]


# ------------------------------------------------------------------
# _build_wiql
# ------------------------------------------------------------------
class TestBuildWiql:
    def test_basic_no_types_no_areas(self) -> None:
        q = _build_wiql("FakeProject", [], [])
        assert "WHERE [System.TeamProject] = 'FakeProject'" in q
        assert "ORDER BY [System.ChangedDate] DESC" in q
        assert "AND" not in q.split("WHERE")[1].split("ORDER")[0].replace(
            "[System.TeamProject] = 'FakeProject'", "")

    def test_with_wit_types(self) -> None:
        q = _build_wiql("Proj", ["Bug", "Task"], [])
        assert "[System.WorkItemType] IN ('Bug', 'Task')" in q

    def test_with_area_paths(self) -> None:
        q = _build_wiql("Proj", [], ["Proj\\Team1", "Proj\\Team2"])
        assert "UNDER 'Proj\\Team1'" in q
        assert "UNDER 'Proj\\Team2'" in q
        assert " OR " in q

    def test_escapes_quotes_in_project(self) -> None:
        q = _build_wiql("Bob's Project", ["Bug"], [])
        assert "Bob''s Project" in q

    def test_escapes_quotes_in_types(self) -> None:
        q = _build_wiql("Proj", ["It's a Bug"], [])
        assert "It''s a Bug" in q

    def test_escapes_quotes_in_area_paths(self) -> None:
        q = _build_wiql("Proj", [], ["Area\\Team's Path"])
        assert "Team''s Path" in q


# ------------------------------------------------------------------
# _parse_row
# ------------------------------------------------------------------
class TestParseRow:
    def _wi_payload(self, **overrides: Any) -> dict[str, Any]:
        fields: dict[str, Any] = {
            "System.Title": "Implement login",
            "System.WorkItemType": "User Story",
            "System.State": "Active",
            "System.BoardColumn": "In Progress",
            "System.BoardLane": "",
            "System.AssignedTo": {"displayName": "Jane Doe"},
            "System.Tags": "api; security",
            "System.IterationPath": "Proj\\Sprint 1",
            "System.AreaPath": "Proj\\Backend",
        }
        fields.update(overrides)
        return {"id": 42, "fields": fields}

    def test_basic_parse(self) -> None:
        row = _parse_row(self._wi_payload())
        assert row.wi_id == 42
        assert row.title == "Implement login"
        assert row.wi_type == "User Story"
        assert row.state == "Active"
        assert row.board_column == "In Progress"
        assert row.assigned_to == "Jane Doe"
        assert row.tags == ["api", "security"]
        assert row.iteration_path == "Proj\\Sprint 1"
        assert row.area_path == "Proj\\Backend"

    def test_assigned_to_string_format(self) -> None:
        row = _parse_row(self._wi_payload(**{"System.AssignedTo": "Plain Name"}))
        assert row.assigned_to == "Plain Name"

    def test_empty_tags(self) -> None:
        row = _parse_row(self._wi_payload(**{"System.Tags": ""}))
        assert row.tags == []

    def test_counts_applied(self) -> None:
        counts = {42: 5}
        row = _parse_row(self._wi_payload(), counts=counts)
        assert row.test_case_count == 5

    def test_counts_missing_id(self) -> None:
        counts = {99: 3}
        row = _parse_row(self._wi_payload(), counts=counts)
        assert row.test_case_count == 0

    def test_intern_fn_called(self) -> None:
        called: list[str] = []

        def fake_intern(s: str) -> str:
            called.append(s)
            return s

        _parse_row(self._wi_payload(), intern_fn=fake_intern)
        # wi_type, state, board_column, board_lane, iteration_path, area_path
        assert "User Story" in called
        assert "Active" in called

    def test_missing_fields_key(self) -> None:
        row = _parse_row({"id": 1})
        assert row.wi_id == 1
        assert row.title == ""
        assert row.tags == []


# ------------------------------------------------------------------
# _is_test_relation
# ------------------------------------------------------------------
class TestIsTestRelation:
    def test_tested_by_forward_ref(self) -> None:
        rel = {"rel": "Microsoft.VSTS.Common.TestedBy-Forward", "attributes": {}}
        assert _is_test_relation(rel) is True

    def test_friendly_name_tested_by(self) -> None:
        rel = {"rel": "SomeCustom", "attributes": {"name": "Tested By"}}
        assert _is_test_relation(rel) is True

    def test_tests_link(self) -> None:
        rel = {"rel": "Microsoft.VSTS.Common.Tests-Reverse", "attributes": {}}
        assert _is_test_relation(rel) is True

    def test_testcase_rel(self) -> None:
        rel = {"rel": "SomeTestCaseLink", "attributes": {}}
        assert _is_test_relation(rel) is True

    def test_unrelated_link(self) -> None:
        rel = {"rel": "System.LinkTypes.Hierarchy-Forward", "attributes": {}}
        assert _is_test_relation(rel) is False

    def test_no_attributes_key(self) -> None:
        rel = {"rel": "Microsoft.VSTS.Common.TestedBy-Forward"}
        assert _is_test_relation(rel) is True


# ------------------------------------------------------------------
# _is_link_relation
# ------------------------------------------------------------------
class TestIsLinkRelation:
    def test_hierarchy_forward(self) -> None:
        rel = {"rel": "System.LinkTypes.Hierarchy-Forward"}
        assert _is_link_relation(rel) is True

    def test_related(self) -> None:
        rel = {"rel": "System.LinkTypes.Related"}
        assert _is_link_relation(rel) is True

    def test_dependency(self) -> None:
        rel = {"rel": "System.LinkTypes.Dependency-Forward"}
        assert _is_link_relation(rel) is True

    def test_artifact_link(self) -> None:
        rel = {"rel": "ArtifactLink"}
        assert _is_link_relation(rel) is False

    def test_tested_by_is_not_link(self) -> None:
        # TestedBy doesn't match hierarchy/related/dependency
        rel = {"rel": "Microsoft.VSTS.Common.TestedBy-Forward"}
        assert _is_link_relation(rel) is False


# ------------------------------------------------------------------
# _rel_target_id
# ------------------------------------------------------------------
class TestRelTargetId:
    def test_valid_url(self) -> None:
        rel = {"url": "https://dev.azure.com/org/proj/_apis/wit/workItems/12345"}
        assert _rel_target_id(rel) == 12345

    def test_url_with_trailing_slash(self) -> None:
        rel = {"url": "https://dev.azure.com/org/proj/_apis/wit/workitems/999/"}
        # regex won't match trailing slash after digits unless re.search finds it
        assert _rel_target_id(rel) == 999

    def test_no_url(self) -> None:
        rel = {"url": ""}
        assert _rel_target_id(rel) == 0

    def test_missing_url_key(self) -> None:
        rel: dict[str, Any] = {}
        assert _rel_target_id(rel) == 0

    def test_url_without_workitems_segment(self) -> None:
        rel = {"url": "https://dev.azure.com/org/proj/_apis/git/repos/abc"}
        assert _rel_target_id(rel) == 0


# ------------------------------------------------------------------
# _count_tested_by
# ------------------------------------------------------------------
class TestCountTestedBy:
    def test_multiple_relations(self) -> None:
        wi: dict[str, Any] = {"relations": [
            {"rel": "Microsoft.VSTS.Common.TestedBy-Forward",
             "url": "https://dev.azure.com/o/p/_apis/wit/workItems/100",
             "attributes": {"name": "Tested By"}},
            {"rel": "Microsoft.VSTS.Common.TestedBy-Forward",
             "url": "https://dev.azure.com/o/p/_apis/wit/workItems/101",
             "attributes": {"name": "Tested By"}},
        ]}
        assert _count_tested_by(wi) == 2

    def test_no_relations_key(self) -> None:
        assert _count_tested_by({}) == 0

    def test_null_relations(self) -> None:
        assert _count_tested_by({"relations": None}) == 0

    def test_mixed_relations(self) -> None:
        wi: dict[str, Any] = {"relations": [
            {"rel": "Microsoft.VSTS.Common.TestedBy-Forward", "attributes": {}},
            {"rel": "System.LinkTypes.Hierarchy-Forward", "attributes": {}},
            {"rel": "ArtifactLink", "attributes": {"name": "Build"}},
        ]}
        assert _count_tested_by(wi) == 1


# ------------------------------------------------------------------
# _classify_relations
# ------------------------------------------------------------------
class TestClassifyRelations:
    def _test_rel(self, target_id: int) -> dict[str, Any]:
        return {
            "rel": "Microsoft.VSTS.Common.TestedBy-Forward",
            "url": f"https://dev.azure.com/o/p/_apis/wit/workItems/{target_id}",
            "attributes": {"name": "Tested By"},
        }

    def _link_rel(self, kind: str, target_id: int) -> dict[str, Any]:
        return {
            "rel": kind,
            "url": f"https://dev.azure.com/o/p/_apis/wit/workItems/{target_id}",
            "attributes": {},
        }

    def test_direct_test_relations(self) -> None:
        rels_by_wi = {
            100: [self._test_rel(200), self._test_rel(201)],
        }
        direct, direct_noid, candidates, all_cand_ids = _classify_relations(rels_by_wi)
        assert direct == {100: {200, 201}}
        assert direct_noid == {}
        assert candidates == {}
        assert all_cand_ids == set()

    def test_link_candidates_separate_from_direct(self) -> None:
        rels_by_wi = {
            100: [
                self._test_rel(200),
                self._link_rel("System.LinkTypes.Hierarchy-Forward", 300),
            ],
        }
        direct, direct_noid, candidates, all_cand_ids = _classify_relations(rels_by_wi)
        assert direct == {100: {200}}
        assert candidates == {100: {300}}
        assert all_cand_ids == {300}

    def test_candidate_overlapping_with_direct_removed(self) -> None:
        # If a target appears in both test and link relations, only direct wins.
        rels_by_wi = {
            100: [
                self._test_rel(200),
                self._link_rel("System.LinkTypes.Related", 200),
            ],
        }
        direct, _, candidates, all_cand_ids = _classify_relations(rels_by_wi)
        assert direct == {100: {200}}
        assert candidates == {}  # 200 removed from candidates

    def test_noid_counted(self) -> None:
        # Test relation without a parseable target ID.
        rel_no_url: dict[str, Any] = {
            "rel": "Microsoft.VSTS.Common.TestedBy-Forward",
            "url": "",
            "attributes": {},
        }
        rels_by_wi = {50: [rel_no_url]}
        _, direct_noid, _, _ = _classify_relations(rels_by_wi)
        assert direct_noid == {50: 1}

    def test_empty_input(self) -> None:
        direct, direct_noid, candidates, all_cand_ids = _classify_relations({})
        assert direct == {}
        assert direct_noid == {}
        assert candidates == {}
        assert all_cand_ids == set()


# ------------------------------------------------------------------
# _tally_test_counts
# ------------------------------------------------------------------
class TestTallyTestCounts:
    def test_direct_only(self) -> None:
        relations_by_wi: dict[int, list[dict[str, Any]]] = {100: []}
        direct = {100: {200, 201}}
        direct_noid: dict[int, int] = {}
        candidates: dict[int, set[int]] = {}
        test_typed: frozenset[int] = frozenset()
        counts = _tally_test_counts(
            relations_by_wi, direct, direct_noid, candidates, test_typed
        )
        assert counts == {100: 2}

    def test_direct_noid_adds(self) -> None:
        relations_by_wi: dict[int, list[dict[str, Any]]] = {100: []}
        direct = {100: {200}}
        direct_noid = {100: 3}
        candidates: dict[int, set[int]] = {}
        test_typed: frozenset[int] = frozenset()
        counts = _tally_test_counts(
            relations_by_wi, direct, direct_noid, candidates, test_typed
        )
        assert counts == {100: 4}  # 1 direct + 3 noid

    def test_candidates_filtered_by_type(self) -> None:
        relations_by_wi: dict[int, list[dict[str, Any]]] = {100: []}
        direct: dict[int, set[int]] = {100: set()}
        direct_noid: dict[int, int] = {}
        candidates = {100: {300, 301, 302}}
        test_typed = frozenset({300, 302})  # 301 is NOT a test type
        counts = _tally_test_counts(
            relations_by_wi, direct, direct_noid, candidates, test_typed
        )
        assert counts == {100: 2}

    def test_zero_total_omitted(self) -> None:
        relations_by_wi: dict[int, list[dict[str, Any]]] = {100: []}
        direct: dict[int, set[int]] = {100: set()}
        direct_noid: dict[int, int] = {}
        candidates: dict[int, set[int]] = {}
        test_typed: frozenset[int] = frozenset()
        counts = _tally_test_counts(
            relations_by_wi, direct, direct_noid, candidates, test_typed
        )
        assert counts == {}  # 0 is not stored


# ------------------------------------------------------------------
# group_rows_by_column
# ------------------------------------------------------------------
class TestGroupRowsByColumn:
    def _row(self, wi_id: int, col: str) -> WorkItemRow:
        return WorkItemRow(
            wi_id=wi_id, title=f"WI-{wi_id}", wi_type="Bug",
            state="Active", board_column=col,
        )

    def test_groups_into_correct_columns(self) -> None:
        cols = [
            BoardColumn(id="1", name="New", column_type="incoming"),
            BoardColumn(id="2", name="Active", column_type="inProgress"),
            BoardColumn(id="3", name="Done", column_type="outgoing"),
        ]
        rows = [self._row(1, "New"), self._row(2, "Active"), self._row(3, "Active")]
        result = group_rows_by_column(rows, cols)
        names = [name for name, _ in result]
        assert names == ["New", "Active", "Done"]
        assert len(result[0][1]) == 1  # New: 1 item
        assert len(result[1][1]) == 2  # Active: 2 items
        assert len(result[2][1]) == 0  # Done: 0 items

    def test_unknown_column_goes_to_extra(self) -> None:
        cols = [BoardColumn(id="1", name="New", column_type="incoming")]
        rows = [self._row(1, "New"), self._row(2, "SomeOtherColumn")]
        result = group_rows_by_column(rows, cols)
        assert result[-1][0] == "(no board column)"
        assert len(result[-1][1]) == 1

    def test_empty_board_column_goes_to_extra(self) -> None:
        cols = [BoardColumn(id="1", name="New", column_type="incoming")]
        rows = [self._row(1, "")]
        result = group_rows_by_column(rows, cols)
        assert result[-1][0] == "(no board column)"

    def test_empty_lanes_preserved(self) -> None:
        cols = [
            BoardColumn(id="1", name="New", column_type="incoming"),
            BoardColumn(id="2", name="Done", column_type="outgoing"),
        ]
        rows: list[WorkItemRow] = []
        result = group_rows_by_column(rows, cols)
        assert len(result) == 2
        assert result[0] == ("New", [])
        assert result[1] == ("Done", [])

    def test_no_extra_bucket_when_all_match(self) -> None:
        cols = [BoardColumn(id="1", name="New", column_type="incoming")]
        rows = [self._row(1, "New")]
        result = group_rows_by_column(rows, cols)
        assert len(result) == 1
        assert result[0][0] == "New"

    def test_rows_sorted_by_id_within_bucket(self) -> None:
        cols = [BoardColumn(id="1", name="Col", column_type="incoming")]
        rows = [self._row(5, "Col"), self._row(2, "Col"), self._row(9, "Col")]
        result = group_rows_by_column(rows, cols)
        ids = [r.wi_id for r in result[0][1]]
        assert ids == [2, 5, 9]


# ------------------------------------------------------------------
# _safe_name
# ------------------------------------------------------------------
class TestSafeName:
    def test_removes_bad_chars(self) -> None:
        assert _safe_name('file<>:"/\\|?*name') == "file_________name"

    def test_empty_returns_file(self) -> None:
        assert _safe_name("") == "file"

    def test_dots_stripped_from_ends(self) -> None:
        assert _safe_name("...name...") == "name"

    def test_spaces_stripped_from_ends(self) -> None:
        assert _safe_name("  padded  ") == "padded"

    def test_truncated_to_180(self) -> None:
        long_name = "a" * 250
        assert len(_safe_name(long_name)) == 180

    def test_none_returns_file(self) -> None:
        # _safe_name receives (name or "") so None would be "" -> "file"
        assert _safe_name("") == "file"


# ------------------------------------------------------------------
# _parse_relations
# ------------------------------------------------------------------
class TestParseRelations:
    def _base_url(self) -> str:
        return "https://dev.azure.com/fakeorg/fakeproj/_apis/wit/workItems"

    def test_attachment_parsed(self) -> None:
        wi: dict[str, Any] = {"relations": [{
            "rel": "AttachedFile",
            "url": "https://dev.azure.com/fakeorg/fakeproj/_apis/wit/attachments/abc",
            "attributes": {
                "name": "report.pdf",
                "resourceSize": 1024,
                "comment": "quarterly report",
            },
        }]}
        attachments, hyperlinks, related = _parse_relations(wi)
        assert len(attachments) == 1
        assert attachments[0].name == "report.pdf"
        assert attachments[0].size == 1024
        assert attachments[0].comment == "quarterly report"
        assert hyperlinks == []
        assert related == []

    def test_hyperlink_parsed(self) -> None:
        wi: dict[str, Any] = {"relations": [{
            "rel": "Hyperlink",
            "url": "https://example.com/docs",
            "attributes": {"comment": "design doc"},
        }]}
        attachments, hyperlinks, related = _parse_relations(wi)
        assert attachments == []
        assert hyperlinks == [("https://example.com/docs", "design doc")]
        assert related == []

    def test_related_work_item_parsed(self) -> None:
        wi: dict[str, Any] = {"relations": [{
            "rel": "System.LinkTypes.Related",
            "url": f"{self._base_url()}/777",
            "attributes": {"name": "Related"},
        }]}
        attachments, hyperlinks, related = _parse_relations(wi)
        assert attachments == []
        assert hyperlinks == []
        assert len(related) == 1
        assert related[0] == ("Related", 777, f"{self._base_url()}/777")

    def test_empty_relations(self) -> None:
        attachments, hyperlinks, related = _parse_relations({})
        assert attachments == []
        assert hyperlinks == []
        assert related == []

    def test_null_relations(self) -> None:
        attachments, hyperlinks, related = _parse_relations({"relations": None})
        assert attachments == []
        assert hyperlinks == []
        assert related == []

    def test_attachment_bad_size(self) -> None:
        wi: dict[str, Any] = {"relations": [{
            "rel": "AttachedFile",
            "url": "https://dev.azure.com/o/p/_apis/wit/attachments/x",
            "attributes": {"name": "f.txt", "resourceSize": "not_a_number"},
        }]}
        attachments, _, _ = _parse_relations(wi)
        assert attachments[0].size == 0

    def test_attachment_name_sanitized(self) -> None:
        wi: dict[str, Any] = {"relations": [{
            "rel": "AttachedFile",
            "url": "https://dev.azure.com/o/p/_apis/wit/attachments/x",
            "attributes": {"name": 'bad<>:file"name', "resourceSize": 0},
        }]}
        attachments, _, _ = _parse_relations(wi)
        assert "<" not in attachments[0].name
        assert ">" not in attachments[0].name

    def test_mixed_relations(self) -> None:
        wi: dict[str, Any] = {"relations": [
            {
                "rel": "AttachedFile",
                "url": "https://dev.azure.com/o/p/_apis/wit/attachments/a1",
                "attributes": {"name": "img.png", "resourceSize": 512},
            },
            {
                "rel": "Hyperlink",
                "url": "https://wiki.example.com",
                "attributes": {"comment": ""},
            },
            {
                "rel": "System.LinkTypes.Hierarchy-Forward",
                "url": f"{self._base_url()}/888",
                "attributes": {"name": "Child"},
            },
        ]}
        attachments, hyperlinks, related = _parse_relations(wi)
        assert len(attachments) == 1
        assert len(hyperlinks) == 1
        assert len(related) == 1
