"""
mcp_bridge.py
MCP server lifecycle management and tool routing for the Testing Toolkit.

Manages the long-running ADO MCP server subprocess (Node.js), converts MCP
tool schemas to Claude tool_use format, and routes tool calls to the server.

Graceful degradation: if the MCP server fails to start, the bridge returns
an empty tool list and logs a warning. The custom tools in chat_tools.py
remain the guaranteed fallback.
"""
from __future__ import annotations

import asyncio
import json
import logging
import shutil
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# ponytail: single event loop thread for all MCP servers; dedicated
# loops per server if contention becomes an issue.


# ---------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------
def _mcp_servers_dir() -> Path:
    """Locate bundled MCP servers directory."""
    mei = getattr(sys, "_MEIPASS", "")
    if mei:
        return Path(mei) / "mcp_servers"
    # Dev: relative to src/core/mcp_bridge.py -> src/mcp_servers/
    return Path(__file__).resolve().parent.parent / "mcp_servers"


def _node_exe() -> Path | None:
    """Find node.exe: bundled first, then system PATH."""
    bundled = _mcp_servers_dir() / "node.exe"
    if bundled.exists():
        return bundled
    which = shutil.which("node")
    return Path(which) if which else None


def _ado_global_entry() -> Path | None:
    """Find the globally-installed @azure-devops/mcp entry point.
    npm global packages on Windows live under AppData/Roaming/npm/node_modules.
    Falls back to checking `npm prefix -g` output."""
    import os
    # Primary: well-known Windows global path
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        entry = (
            Path(appdata) / "npm" / "node_modules"
            / "@azure-devops" / "mcp" / "dist" / "index.js"
        )
        if entry.exists():
            return entry
    # Fallback: ask npm for its global prefix
    npm = shutil.which("npm")
    if npm:
        import subprocess
        _sp_kwargs: dict[str, object] = {}
        if sys.platform == "win32":
            _si = subprocess.STARTUPINFO()
            _si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            _si.wShowWindow = 0
            _sp_kwargs = {
                "startupinfo": _si,
                "creationflags": subprocess.CREATE_NO_WINDOW,
            }
        try:
            result = subprocess.run(
                [npm, "prefix", "-g"],
                capture_output=True, text=True, timeout=10,
                **_sp_kwargs,
            )
            prefix = result.stdout.strip()
            if prefix:
                entry = (
                    Path(prefix) / "node_modules"
                    / "@azure-devops" / "mcp" / "dist" / "index.js"
                )
                if entry.exists():
                    return entry
        except (OSError, subprocess.TimeoutExpired):
            pass
    return None


# ---------------------------------------------------------------------
# Schema conversion
# ---------------------------------------------------------------------
def mcp_tool_to_claude_schema(mcp_tool: Any) -> dict[str, Any]:
    """Convert an MCP Tool object to Claude tool_use format."""
    schema = getattr(mcp_tool, "inputSchema", None)
    if schema is None:
        schema = {"type": "object", "properties": {}}
    elif hasattr(schema, "model_dump"):
        schema = schema.model_dump(exclude_none=True)
    elif not isinstance(schema, dict):
        schema = {"type": "object", "properties": {}}
    return {
        "name": mcp_tool.name,
        "description": getattr(mcp_tool, "description", "") or "",
        "input_schema": schema,
    }


# ---------------------------------------------------------------------
# Server config
# ---------------------------------------------------------------------
@dataclass(slots=True)
class MCPServerConfig:
    """Configuration for one MCP server."""
    server_id: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    tool_filter: set[str] | None = None


# ---------------------------------------------------------------------
# Single server manager
# ---------------------------------------------------------------------
class MCPServerManager:
    """Manages a single MCP server subprocess and its client session."""

    def __init__(self, config: MCPServerConfig) -> None:
        self._config = config
        self._session: Any = None
        self._exit_stack: Any = None
        self._tools: list[dict[str, Any]] = []
        self._tool_names: set[str] = set()
        self._healthy = False

    @property
    def server_id(self) -> str:
        return self._config.server_id

    @property
    def is_healthy(self) -> bool:
        return self._healthy and self._session is not None

    @property
    def tools(self) -> list[dict[str, Any]]:
        return self._tools

    @property
    def tool_names(self) -> set[str]:
        return self._tool_names

    async def start(self) -> bool:
        """Start the MCP server subprocess and initialize session."""
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
            from contextlib import AsyncExitStack

            params = StdioServerParameters(
                command=self._config.command,
                args=self._config.args,
                env=self._config.env or None,
            )

            self._exit_stack = AsyncExitStack()
            transport = await self._exit_stack.enter_async_context(
                stdio_client(params)
            )
            read_stream, write_stream = transport

            self._session = await self._exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            await self._session.initialize()

            # List and convert tools
            response = await self._session.list_tools()
            raw_tools = response.tools if response else []

            self._tools = []
            self._tool_names = set()
            for t in raw_tools:
                # Apply filter if set
                if self._config.tool_filter and t.name not in self._config.tool_filter:
                    continue
                schema = mcp_tool_to_claude_schema(t)
                self._tools.append(schema)
                self._tool_names.add(t.name)

            self._healthy = True
            log.info(
                "[INFO] MCP server '%s' started: %d tools available",
                self._config.server_id, len(self._tools),
            )
            return True

        except Exception as e:
            log.warning(
                "[WARN] MCP server '%s' failed to start: %s",
                self._config.server_id, e,
            )
            self._healthy = False
            await self._cleanup()
            return False

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Invoke a tool. Returns JSON string result."""
        if not self.is_healthy or name not in self._tool_names:
            return json.dumps({"error": f"Tool '{name}' unavailable"})
        try:
            result = await self._session.call_tool(name, arguments)
            # MCP returns content blocks - extract text
            parts: list[str] = []
            for block in (result.content if result else []):
                if hasattr(block, "text"):
                    parts.append(block.text)
                elif hasattr(block, "data"):
                    parts.append(str(block.data))
            return "\n".join(parts) if parts else json.dumps({"result": "ok"})
        except Exception as e:
            log.warning(
                "[WARN] MCP tool '%s' call failed: %s", name, e,
            )
            return json.dumps({"error": str(e)})

    async def stop(self) -> None:
        """Graceful shutdown."""
        self._healthy = False
        await self._cleanup()

    async def _cleanup(self) -> None:
        if self._exit_stack:
            try:
                await self._exit_stack.aclose()
            except Exception:
                pass
            self._exit_stack = None
            self._session = None


# ---------------------------------------------------------------------
# Bridge (orchestrates multiple servers)
# ---------------------------------------------------------------------
class MCPBridge:
    """Orchestrates multiple MCP servers. Thread-safe interface for
    the AgenticStreamWorker to call tools."""

    def __init__(self) -> None:
        self._servers: dict[str, MCPServerManager] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._started = False

    @property
    def is_ready(self) -> bool:
        return self._started and self._ready.is_set()

    def start_servers(self, configs: list[MCPServerConfig]) -> None:
        """Start all configured MCP servers in a background thread.
        Non-blocking - returns immediately."""
        if self._started:
            return
        self._started = True

        def _run() -> None:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            try:
                self._loop.run_until_complete(self._start_all(configs))
            except Exception as e:
                log.warning("[WARN] MCP bridge startup error: %s", e)
            finally:
                self._ready.set()
            # Keep loop alive for call_tool submissions
            try:
                self._loop.run_forever()
            except Exception:
                pass

        self._thread = threading.Thread(target=_run, daemon=True, name="mcp-bridge")
        self._thread.start()

    async def _start_all(self, configs: list[MCPServerConfig]) -> None:
        """Start each server sequentially (low memory footprint)."""
        for cfg in configs:
            mgr = MCPServerManager(cfg)
            ok = await mgr.start()
            if ok:
                self._servers[cfg.server_id] = mgr

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """All tools from all healthy servers (Claude format).
        Thread-safe, no async needed."""
        if not self.is_ready:
            return []
        tools: list[dict[str, Any]] = []
        for mgr in self._servers.values():
            if mgr.is_healthy:
                tools.extend(mgr.tools)
        return tools

    def has_tool(self, name: str) -> bool:
        """Check if any server owns this tool name."""
        for mgr in self._servers.values():
            if mgr.is_healthy and name in mgr.tool_names:
                return True
        return False

    def call_tool(self, name: str, arguments: dict[str, Any]) -> str | None:
        """Route a tool call to the correct server.
        Returns None if no server owns this tool name.
        Thread-safe - submits to the bridge event loop."""
        if not self._loop or not self.is_ready:
            return None

        for mgr in self._servers.values():
            if mgr.is_healthy and name in mgr.tool_names:
                future = asyncio.run_coroutine_threadsafe(
                    mgr.call_tool(name, arguments), self._loop,
                )
                try:
                    return future.result(timeout=120)
                except Exception as e:
                    return json.dumps({"error": str(e)})
        return None

    def stop_all(self) -> None:
        """Stop all servers and join the event loop thread."""
        if not self._loop:
            return
        # Schedule stop for each server
        for mgr in list(self._servers.values()):
            asyncio.run_coroutine_threadsafe(mgr.stop(), self._loop)
        # Stop the event loop
        self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._servers.clear()
        self._started = False


# ---------------------------------------------------------------------
# Config builder (creates MCPServerConfig from ToolContext fields)
# ---------------------------------------------------------------------
def build_mcp_configs(
    ado_org: str = "",
    ado_pat: str = "",
    ado_project: str = "",
    ado_url: str = "",
) -> list[MCPServerConfig]:
    """Build MCP server configs based on available credentials.
    Returns only configs for servers that CAN be started."""
    configs: list[MCPServerConfig] = []

    # ADO MCP (Node.js via globally-installed @azure-devops/mcp)
    node = _node_exe()
    entry = _ado_global_entry()
    if node and entry and ado_org and ado_pat:
        base_url = ado_url or f"https://dev.azure.com/{ado_org}"
        configs.append(MCPServerConfig(
            server_id="ado",
            command=str(node),
            args=[str(entry)],
            env={
                "AZURE_DEVOPS_URL": base_url,
                "AZURE_DEVOPS_PAT": ado_pat,
                "AZURE_DEVOPS_PROJECT": ado_project,
                "AZURE_DEVOPS_COLLECTION": "DefaultCollection",
            },
            # Accept all tools (server is read-only anyway)
            tool_filter=None,
        ))

    return configs
