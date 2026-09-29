"""
CORD MCP - Model Context Protocol Stdio Client
Implements JSON-RPC 2.0 over stdio for connecting to external MCP servers.
"""

from __future__ import annotations
import json
import asyncio
from typing import Dict, Any, List, Optional
from pathlib import Path

from cord.ui.console import ui


class MCPStdioClient:
    """Connects to an MCP server via child process stdin/stdout."""

    def __init__(self, name: str, command: str, args: List[str], env: Optional[Dict[str, str]] = None):
        self.name = name
        self.command = command
        self.args = args
        self.env = env
        self.process: Optional[asyncio.subprocess.Process] = None
        self._request_id = 0
        self._pending_requests: Dict[int, asyncio.Future] = {}
        self._reader_task: Optional[asyncio.Task] = None
        self.tools: List[Dict[str, Any]] = []

    async def start(self) -> bool:
        """Launches the MCP server subprocess and performs initialization handshake."""
        try:
            cmd = [self.command] + self.args
            self.process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self.env,
            )

            # Start reading responses in background
            self._reader_task = asyncio.create_task(self._listen_stdout())

            # Perform initialize request
            init_res = await self._send_request(
                "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "clientInfo": {"name": "cord-cli", "version": "1.0.0"},
                },
                timeout=10.0,
            )

            # Send initialized notification
            await self._send_notification("notifications/initialized", {})

            # Fetch tools
            tools_res = await self._send_request("tools/list", {}, timeout=10.0)
            self.tools = tools_res.get("tools", [])

            ui.print_success(f"Connected to MCP server '{self.name}' ({len(self.tools)} tool(s) registered).")
            return True

        except Exception as e:
            ui.print_warning(f"Could not start MCP server '{self.name}': {e}")
            await self.stop()
            return False

    async def _send_request(self, method: str, params: Dict[str, Any], timeout: float = 30.0) -> Dict[str, Any]:
        if not self.process or not self.process.stdin:
            raise RuntimeError("MCP process not running.")

        self._request_id += 1
        req_id = self._request_id
        payload = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params,
        }

        fut = asyncio.get_running_loop().create_future()
        self._pending_requests[req_id] = fut

        line = json.dumps(payload) + "\n"
        self.process.stdin.write(line.encode("utf-8"))
        await self.process.stdin.drain()

        try:
            return await asyncio.wait_for(fut, timeout=timeout)
        finally:
            self._pending_requests.pop(req_id, None)

    async def _send_notification(self, method: str, params: Dict[str, Any]) -> None:
        if not self.process or not self.process.stdin:
            return
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }
        line = json.dumps(payload) + "\n"
        self.process.stdin.write(line.encode("utf-8"))
        await self.process.stdin.drain()

    async def _listen_stdout(self) -> None:
        if not self.process or not self.process.stdout:
            return

        while True:
            line = await self.process.stdout.readline()
            if not line:
                break
            try:
                data = json.loads(line.decode("utf-8").strip())
                if "id" in data:
                    try:
                        req_id = int(data["id"])
                    except (ValueError, TypeError):
                        req_id = data["id"]
                    if req_id in self._pending_requests:
                        fut = self._pending_requests[req_id]
                        if not fut.done():
                            if "error" in data:
                                fut.set_exception(Exception(data["error"]))
                            else:
                                fut.set_result(data.get("result", {}))
            except Exception:
                continue

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Invokes a tool on this MCP server."""
        res = await self._send_request(
            "tools/call",
            {"name": tool_name, "arguments": arguments},
        )
        content = res.get("content", [])
        if isinstance(content, list):
            texts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
            return "\n".join(texts) if texts else str(content)
        return str(res)

    async def stop(self) -> None:
        if self._reader_task:
            self._reader_task.cancel()
        if self.process:
            try:
                self.process.terminate()
                await self.process.wait()
            except Exception:
                pass
            self.process = None
