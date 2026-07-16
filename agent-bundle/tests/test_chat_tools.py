"""
test_chat_tools.py
Tests for core.chat_tools: tool definition schema correctness, dispatch,
and get_tool_definitions logic branches.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from core.chat_tools import (
    ToolContext,
    _ADO_TOOLS,
    _HANDLERS,
    _json_result,
    execute_tool,
    get_tool_definitions,
)
from core.runtime_config import RuntimeConfig


# -- Sentinel credentials (unmistakably fake) --------------------------------
_FAKE_PAT = "FAKE-PAT-000000000000000000000000000000000000"
_FAKE_ORG = "fake-org-sentinel"
_FAKE_PROJECT = "fake-project-sentinel"


# -- Fixtures ----------------------------------------------------------------

@pytest.fixture()
def ado_cfg() -> RuntimeConfig:
    """RuntimeConfig with fake sentinel credentials."""
    return RuntimeConfig(
        pat=_FAKE_PAT,
        organization=_FAKE_ORG,
        project=_FAKE_PROJECT,
        http_timeout_sec=5.0,
        tls_mode="off",
    )


@pytest.fixture()
def ctx_with_ado(ado_cfg: RuntimeConfig) -> ToolContext:
    """ToolContext that reports has_ado=True, no MCP bridge."""
    return ToolContext(
        ado_org=_FAKE_ORG,
        ado_project=_FAKE_PROJECT,
        ado_cfg=ado_cfg,
        mcp_bridge=None,
    )


@pytest.fixture()
def ctx_empty() -> ToolContext:
    """ToolContext with nothing configured."""
    return ToolContext()


# -- Valid JSON Schema types for property validation --------------------------
_VALID_JSON_SCHEMA_TYPES = frozenset(
    {"string", "integer", "number", "boolean", "object", "array", "null"}
)


# =============================================================================
# Schema correctness tests
# =============================================================================

class TestToolDefinitionSchema:
    """Each tool definition must conform to the Claude API tools schema."""

    def test_ado_tools_is_nonempty_list(self) -> None:
        assert isinstance(_ADO_TOOLS, list)
        assert len(_ADO_TOOLS) > 0

    @pytest.mark.parametrize("tool", _ADO_TOOLS, ids=[t["name"] for t in _ADO_TOOLS])
    def test_required_top_level_keys(self, tool: dict[str, Any]) -> None:
        """Every tool must have name, description, and input_schema."""
        assert "name" in tool, "missing 'name'"
        assert "description" in tool, "missing 'description'"
        assert "input_schema" in tool, "missing 'input_schema'"

    @pytest.mark.parametrize("tool", _ADO_TOOLS, ids=[t["name"] for t in _ADO_TOOLS])
    def test_name_is_nonempty_string(self, tool: dict[str, Any]) -> None:
        assert isinstance(tool["name"], str)
        assert len(tool["name"]) > 0

    @pytest.mark.parametrize("tool", _ADO_TOOLS, ids=[t["name"] for t in _ADO_TOOLS])
    def test_description_is_nonempty_string(self, tool: dict[str, Any]) -> None:
        assert isinstance(tool["description"], str)
        assert len(tool["description"]) > 0

    @pytest.mark.parametrize("tool", _ADO_TOOLS, ids=[t["name"] for t in _ADO_TOOLS])
    def test_input_schema_is_object_type(self, tool: dict[str, Any]) -> None:
        schema = tool["input_schema"]
        assert isinstance(schema, dict)
        assert schema.get("type") == "object"

    @pytest.mark.parametrize("tool", _ADO_TOOLS, ids=[t["name"] for t in _ADO_TOOLS])
    def test_input_schema_has_properties(self, tool: dict[str, Any]) -> None:
        schema = tool["input_schema"]
        assert "properties" in schema
        assert isinstance(schema["properties"], dict)
        assert len(schema["properties"]) > 0

    @pytest.mark.parametrize("tool", _ADO_TOOLS, ids=[t["name"] for t in _ADO_TOOLS])
    def test_required_is_list_of_strings(self, tool: dict[str, Any]) -> None:
        schema = tool["input_schema"]
        assert "required" in schema
        required = schema["required"]
        assert isinstance(required, list)
        assert all(isinstance(r, str) for r in required)

    @pytest.mark.parametrize("tool", _ADO_TOOLS, ids=[t["name"] for t in _ADO_TOOLS])
    def test_required_fields_exist_in_properties(self, tool: dict[str, Any]) -> None:
        schema = tool["input_schema"]
        props = set(schema["properties"].keys())
        for req in schema["required"]:
            assert req in props, f"required field '{req}' not in properties"

    @pytest.mark.parametrize("tool", _ADO_TOOLS, ids=[t["name"] for t in _ADO_TOOLS])
    def test_property_types_are_valid(self, tool: dict[str, Any]) -> None:
        """All property types must be valid JSON Schema types."""
        for prop_name, prop_def in tool["input_schema"]["properties"].items():
            assert "type" in prop_def, (
                f"property '{prop_name}' missing 'type'"
            )
            assert prop_def["type"] in _VALID_JSON_SCHEMA_TYPES, (
                f"property '{prop_name}' has invalid type '{prop_def['type']}'"
            )

    @pytest.mark.parametrize("tool", _ADO_TOOLS, ids=[t["name"] for t in _ADO_TOOLS])
    def test_properties_have_descriptions(self, tool: dict[str, Any]) -> None:
        """Each property should have a description string."""
        for prop_name, prop_def in tool["input_schema"]["properties"].items():
            assert "description" in prop_def, (
                f"property '{prop_name}' missing 'description'"
            )
            assert isinstance(prop_def["description"], str)
            assert len(prop_def["description"]) > 0


class TestNoDuplicateToolNames:
    """Tool name uniqueness."""

    def test_no_duplicate_names_in_ado_tools(self) -> None:
        names = [t["name"] for t in _ADO_TOOLS]
        assert len(names) == len(set(names)), "duplicate tool names detected"

    def test_all_handler_names_have_definitions(self) -> None:
        """Every handler in the dispatch table has a matching definition."""
        defined_names = {t["name"] for t in _ADO_TOOLS}
        for handler_name in _HANDLERS:
            assert handler_name in defined_names, (
                f"handler '{handler_name}' has no tool definition"
            )

    def test_all_definitions_have_handlers(self) -> None:
        """Every tool definition has a matching handler in the dispatch table."""
        for tool in _ADO_TOOLS:
            assert tool["name"] in _HANDLERS, (
                f"tool '{tool['name']}' has no handler"
            )


# =============================================================================
# ToolContext tests
# =============================================================================

class TestToolContext:
    """ToolContext dataclass and has_ado property."""

    def test_has_ado_true_when_all_set(self, ctx_with_ado: ToolContext) -> None:
        assert ctx_with_ado.has_ado is True

    def test_has_ado_false_when_empty(self, ctx_empty: ToolContext) -> None:
        assert ctx_empty.has_ado is False

    def test_has_ado_false_missing_org(self, ado_cfg: RuntimeConfig) -> None:
        ctx = ToolContext(
            ado_org="",
            ado_project=_FAKE_PROJECT,
            ado_cfg=ado_cfg,
        )
        assert ctx.has_ado is False

    def test_has_ado_false_missing_project(self, ado_cfg: RuntimeConfig) -> None:
        ctx = ToolContext(
            ado_org=_FAKE_ORG,
            ado_project="",
            ado_cfg=ado_cfg,
        )
        assert ctx.has_ado is False

    def test_has_ado_false_missing_cfg(self) -> None:
        ctx = ToolContext(
            ado_org=_FAKE_ORG,
            ado_project=_FAKE_PROJECT,
            ado_cfg=None,
        )
        assert ctx.has_ado is False


# =============================================================================
# get_tool_definitions tests
# =============================================================================

class TestGetToolDefinitions:
    """Branching logic in get_tool_definitions."""

    def test_returns_ado_tools_when_has_ado(
        self, ctx_with_ado: ToolContext
    ) -> None:
        result = get_tool_definitions(ctx_with_ado)
        assert len(result) == len(_ADO_TOOLS)
        names = {t["name"] for t in result}
        for t in _ADO_TOOLS:
            assert t["name"] in names

    def test_returns_empty_when_no_ado_no_bridge(
        self, ctx_empty: ToolContext
    ) -> None:
        result = get_tool_definitions(ctx_empty)
        assert result == []

    def test_mcp_bridge_ready_returns_mcp_tools(
        self, ctx_with_ado: ToolContext
    ) -> None:
        """When MCP bridge is ready and has tools, those take priority."""
        mock_bridge = MagicMock()
        mock_bridge.is_ready = True
        mock_bridge.get_tool_definitions.return_value = [
            {
                "name": "mcp_tool_alpha",
                "description": "An MCP tool",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            }
        ]
        ctx_with_ado.mcp_bridge = mock_bridge

        with patch("core.chat_tools.MCPBridge", create=True):
            # The function does `from core.mcp_bridge import MCPBridge`
            # inside; patch the import target.
            with patch.dict(
                "sys.modules",
                {"core.mcp_bridge": MagicMock(MCPBridge=type(mock_bridge))},
            ):
                result = get_tool_definitions(ctx_with_ado)

        # Should include the MCP tool
        names = {t["name"] for t in result}
        assert "mcp_tool_alpha" in names
        # ADO tools that are NOT in MCP should also appear (dedup merge)
        for t in _ADO_TOOLS:
            assert t["name"] in names

    def test_mcp_bridge_ready_deduplicates_by_name(
        self, ctx_with_ado: ToolContext
    ) -> None:
        """If MCP already exposes a tool with the same name, do not duplicate."""
        # Simulate MCP exposing 'ado_run_wiql' -- our custom one should NOT
        # be added a second time.
        mock_bridge = MagicMock()
        mock_bridge.is_ready = True
        mock_bridge.get_tool_definitions.return_value = [
            {
                "name": "ado_run_wiql",
                "description": "MCP version of wiql",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            }
        ]
        ctx_with_ado.mcp_bridge = mock_bridge

        with patch.dict(
            "sys.modules",
            {"core.mcp_bridge": MagicMock(MCPBridge=type(mock_bridge))},
        ):
            result = get_tool_definitions(ctx_with_ado)

        wiql_entries = [t for t in result if t["name"] == "ado_run_wiql"]
        assert len(wiql_entries) == 1
        # Should be the MCP version (first wins)
        assert wiql_entries[0]["description"] == "MCP version of wiql"

    def test_mcp_bridge_not_ready_falls_through(
        self, ctx_with_ado: ToolContext
    ) -> None:
        """If bridge exists but is_ready=False, fall through to custom tools."""
        mock_bridge = MagicMock()
        mock_bridge.is_ready = False
        ctx_with_ado.mcp_bridge = mock_bridge

        with patch.dict(
            "sys.modules",
            {"core.mcp_bridge": MagicMock(MCPBridge=type(mock_bridge))},
        ):
            result = get_tool_definitions(ctx_with_ado)

        assert len(result) == len(_ADO_TOOLS)

    def test_mcp_bridge_exception_falls_through(
        self, ctx_with_ado: ToolContext
    ) -> None:
        """If bridge raises, fall through to custom tools gracefully."""
        mock_bridge = MagicMock()
        mock_bridge.is_ready = True
        mock_bridge.get_tool_definitions.side_effect = RuntimeError("boom")
        ctx_with_ado.mcp_bridge = mock_bridge

        with patch.dict(
            "sys.modules",
            {"core.mcp_bridge": MagicMock(MCPBridge=type(mock_bridge))},
        ):
            result = get_tool_definitions(ctx_with_ado)

        # Should still get the fallback tools
        assert len(result) == len(_ADO_TOOLS)

    def test_mcp_bridge_empty_tools_falls_through(
        self, ctx_with_ado: ToolContext
    ) -> None:
        """If bridge returns empty list, fall through to custom tools."""
        mock_bridge = MagicMock()
        mock_bridge.is_ready = True
        mock_bridge.get_tool_definitions.return_value = []
        ctx_with_ado.mcp_bridge = mock_bridge

        with patch.dict(
            "sys.modules",
            {"core.mcp_bridge": MagicMock(MCPBridge=type(mock_bridge))},
        ):
            result = get_tool_definitions(ctx_with_ado)

        assert len(result) == len(_ADO_TOOLS)


# =============================================================================
# execute_tool tests
# =============================================================================

class TestExecuteTool:
    """Dispatch logic in execute_tool."""

    def test_unknown_tool_returns_error(self, ctx_with_ado: ToolContext) -> None:
        result = execute_tool("nonexistent_tool", {}, ctx_with_ado)
        assert "error" in result
        assert "Unknown tool" in result

    def test_handler_exception_returns_error_json(
        self, ctx_with_ado: ToolContext
    ) -> None:
        """If a handler raises, execute_tool returns error JSON (never raises)."""
        with patch.dict(_HANDLERS, {"boom_tool": lambda p, c: 1 / 0}):
            result = execute_tool("boom_tool", {}, ctx_with_ado)
        assert "error" in result
        assert "division by zero" in result

    def test_mcp_bridge_dispatches_first(
        self, ctx_with_ado: ToolContext
    ) -> None:
        """MCP bridge is tried before custom handlers."""
        mock_bridge = MagicMock()
        mock_bridge.has_tool.return_value = True
        mock_bridge.call_tool.return_value = '{"mcp": true}'
        ctx_with_ado.mcp_bridge = mock_bridge

        with patch.dict(
            "sys.modules",
            {"core.mcp_bridge": MagicMock(MCPBridge=type(mock_bridge))},
        ):
            result = execute_tool("ado_run_wiql", {"query": "SELECT ..."}, ctx_with_ado)

        assert result == '{"mcp": true}'
        mock_bridge.call_tool.assert_called_once()

    def test_mcp_bridge_returns_none_falls_to_handler(
        self, ctx_with_ado: ToolContext
    ) -> None:
        """If bridge.call_tool returns None, falls through to custom handler."""
        mock_bridge = MagicMock()
        mock_bridge.has_tool.return_value = True
        mock_bridge.call_tool.return_value = None
        ctx_with_ado.mcp_bridge = mock_bridge

        # Patch the actual handler so it does not hit the network.
        with patch.dict(
            "sys.modules",
            {"core.mcp_bridge": MagicMock(MCPBridge=type(mock_bridge))},
        ):
            with patch.dict(
                _HANDLERS,
                {"ado_run_wiql": lambda p, c: '{"fallback": true}'},
            ):
                result = execute_tool(
                    "ado_run_wiql", {"query": "SELECT ..."}, ctx_with_ado
                )

        assert '"fallback": true' in result

    def test_mcp_bridge_exception_returns_error(
        self, ctx_with_ado: ToolContext
    ) -> None:
        """If bridge raises, returns error JSON."""
        mock_bridge = MagicMock()
        mock_bridge.has_tool.side_effect = RuntimeError("bridge broke")
        ctx_with_ado.mcp_bridge = mock_bridge

        with patch.dict(
            "sys.modules",
            {"core.mcp_bridge": MagicMock(MCPBridge=type(mock_bridge))},
        ):
            result = execute_tool("ado_run_wiql", {}, ctx_with_ado)

        assert "error" in result
        assert "bridge broke" in result


# =============================================================================
# _json_result helper tests
# =============================================================================

class TestJsonResult:
    """Serialization helper."""

    def test_string_passthrough(self) -> None:
        assert _json_result("hello") == "hello"

    def test_dict_serialized(self) -> None:
        import json
        result = _json_result({"key": "value"})
        parsed = json.loads(result)
        assert parsed == {"key": "value"}

    def test_list_serialized(self) -> None:
        import json
        result = _json_result([1, 2, 3])
        parsed = json.loads(result)
        assert parsed == [1, 2, 3]

    def test_non_serializable_uses_str(self) -> None:
        """default=str handles non-JSON-serializable types."""
        from pathlib import Path
        import json
        result = _json_result({"path": Path("/tmp/foo")})
        parsed = json.loads(result)
        # Path should be stringified
        assert "/tmp/foo" in parsed["path"] or "\\tmp\\foo" in parsed["path"]

    def test_ensure_ascii(self) -> None:
        result = _json_result({"msg": "café"})
        # ensure_ascii=True means no raw unicode bytes
        assert "\\u" in result or "cafe" in result
