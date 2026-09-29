"""CORD MCP - Model Context Protocol Stdio Server
Exposes CORD's native tool suite to external clients (Claude Desktop, Cursor, Antigravity, etc.)
over standard JSON-RPC 2.0 stdio protocol.
"""
from __future__ import annotations
import sys
import json
import asyncio
from typing import Dict, Any, Optional

from cord.core.config import ConfigManager
from cord.core.permissions import PermissionGuard
from cord.tools.registry import ToolRegistry
from cord.tools import get_default_tools


class MCPServer:
    """Stdio-based Model Context Protocol server exposing CORD tools."""

    def __init__(self, tool_registry: Optional[ToolRegistry] = None) -> None:
        if tool_registry:
            self.tools = tool_registry
        else:
            cfg = ConfigManager().config
            guard = PermissionGuard(cfg)
            self.tools = ToolRegistry(guard)
            self.tools.register_many(get_default_tools())

    def get_tool_definitions(self) -> list[Dict[str, Any]]:
        defs = []
        for t in self.tools.tools.values():
            if hasattr(t, "get_schema"):
                schema = t.get_schema()
            elif hasattr(t, "parameters"):
                schema = t.parameters
            elif hasattr(t, "to_schema"):
                schema = t.to_schema().get("parameters", {})
            else:
                schema = {}

            defs.append({
                "name": t.name,
                "description": getattr(t, "description", ""),
                "inputSchema": schema,
            })
        return defs

    async def handle_request(self, req: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        req_id = req.get("id")
        method = req.get("method")
        params = req.get("params", {})

        # Handle notifications (no id)
        if req_id is None:
            return None

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {
                            "listChanged": False,
                        },
                    },
                    "serverInfo": {
                        "name": "cord-mcp-server",
                        "version": "1.0.0",
                    },
                },
            }

        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": self.get_tool_definitions(),
                },
            }

        elif method == "tools/call":
            tool_name = params.get("name", "")
            tool_args = params.get("arguments", {})
            try:
                res = await self.tools.execute(tool_name, tool_args)
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {"type": "text", "text": res.to_string()}
                        ],
                        "isError": not res.success,
                    },
                }
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {"type": "text", "text": f"Error executing tool '{tool_name}': {e}"}
                        ],
                        "isError": True,
                    },
                }

        elif method == "ping":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {},
            }

        else:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}",
                },
            }

    async def run_stdio(self) -> None:
        """Main stdio loop reading JSON-RPC messages line-by-line."""
        loop = asyncio.get_running_loop()
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)

        while True:
            line_bytes = await reader.readline()
            if not line_bytes:
                break

            line = line_bytes.decode("utf-8").strip()
            if not line:
                continue

            try:
                req = json.loads(line)
            except json.JSONDecodeError:
                continue

            resp = await self.handle_request(req)
            if resp is not None:
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()


def run_mcp_server() -> None:
    server = MCPServer()
    asyncio.run(server.run_stdio())


if __name__ == "__main__":
    run_mcp_server()
