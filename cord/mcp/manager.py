"""
CORD MCP - MCP Server Manager
Loads MCP server configurations from mcp.json and bridges MCP tools into CORD's ToolRegistry.
"""

from __future__ import annotations
import json
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional

from cord.mcp.client import MCPStdioClient
from cord.tools.base import BaseTool, ToolResult
from cord.ui.console import ui


class MCPWrappedTool(BaseTool):
    """Wraps an MCP tool as a CORD BaseTool."""

    def __init__(self, server_name: str, client: MCPStdioClient, tool_meta: Dict[str, Any]):
        self.server_name = server_name
        self.client = client
        # Prefix with mcp_server_ to prevent name collisions
        self.name = f"mcp_{server_name}_{tool_meta['name']}"
        self.description = f"[MCP: {server_name}] {tool_meta.get('description', '')}"
        self.parameters = tool_meta.get("inputSchema", {"type": "object", "properties": {}})
        self.original_name = tool_meta["name"]

    async def execute(self, **kwargs) -> ToolResult:
        try:
            out = await self.client.call_tool(self.original_name, kwargs)
            return ToolResult(success=True, output=str(out))
        except Exception as e:
            return ToolResult(success=False, output="", error=f"MCP Tool Error: {e}")


class MCPManager:
    """Manages external MCP servers and provides tools to the agent."""

    def __init__(self, workspace_path: Optional[Path] = None):
        self.workspace_path = workspace_path or Path.cwd()
        self.clients: Dict[str, MCPStdioClient] = {}
        self.tools: Dict[str, BaseTool] = {}

    def get_config_paths(self) -> List[Path]:
        return [
            Path.home() / ".cord" / "mcp.json",
            self.workspace_path / ".cord" / "mcp.json",
            self.workspace_path / "cord_mcp.json",
        ]

    def load_servers_config(self) -> Dict[str, Any]:
        """Merges MCP configs from standard locations."""
        servers = {}
        for p in self.get_config_paths():
            if p.exists():
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if "mcpServers" in data:
                            servers.update(data["mcpServers"])
                except Exception as e:
                    ui.print_warning(f"Error reading MCP config from {p}: {e}")
        return servers

    async def initialize_all(self) -> None:
        """Starts all configured MCP servers."""
        configs = self.load_servers_config()
        if not configs:
            return

        ui.print_info(f"Connecting to {len(configs)} configured MCP server(s)...")

        for s_name, s_cfg in configs.items():
            cmd = s_cfg.get("command")
            args = s_cfg.get("args", [])
            env = s_cfg.get("env")

            if not cmd:
                continue

            client = MCPStdioClient(name=s_name, command=cmd, args=args, env=env)
            success = await client.start()
            if success:
                self.clients[s_name] = client
                for t in client.tools:
                    wrapped = MCPWrappedTool(server_name=s_name, client=client, tool_meta=t)
                    self.tools[wrapped.name] = wrapped

    def get_tools(self) -> List[BaseTool]:
        return list(self.tools.values())

    async def shutdown_all(self) -> None:
        for client in self.clients.values():
            await client.stop()
        self.clients.clear()
        self.tools.clear()
