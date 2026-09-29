"""
CORD Tools - Central Tool Registry & Interceptor
Validates permissions, runs tools, formats outputs, and provides schemas to the LLM.
"""

from __future__ import annotations
import json
import asyncio
from typing import Dict, Any, List, Optional

from cord.tools.base import BaseTool, ToolResult
from cord.core.permissions import PermissionGuard
from cord.ui.console import ui


class ToolRegistry:
    """Central repository for all agent-callable tools."""

    def __init__(self, permission_guard: PermissionGuard):
        self.permission_guard = permission_guard
        self.tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self.tools[tool.name] = tool

    def register_many(self, tools: List[BaseTool]) -> None:
        for t in tools:
            self.register(t)

    def get(self, name: str) -> Optional[BaseTool]:
        return self.tools.get(name)

    def get_schemas(self) -> List[Dict[str, Any]]:
        """Returns JSON schemas for all registered tools."""
        return [t.to_schema() for t in self.tools.values()]

    async def execute(self, tool_name: str, args: Dict[str, Any]) -> ToolResult:
        """Checks permissions with PermissionGuard, then executes tool."""
        tool = self.tools.get(tool_name)
        if not tool:
            from cord.subagents.base_subagent import TOOL_ALIASES
            alias_target = TOOL_ALIASES.get(tool_name)
            if alias_target and alias_target in self.tools:
                tool = self.tools.get(alias_target)

        if not tool:
            if tool_name in ("think", "thought", "reasoning", "internal_thought"):
                thought_val = args.get("thought") or args.get("text") or args.get("reasoning") or ""
                return ToolResult(
                    success=True,
                    output="Thought acknowledged. Please proceed directly with user response or real tool calls.",
                    metadata={"thought": str(thought_val)},
                )
            return ToolResult(success=False, output="", error=f"Unknown tool: '{tool_name}'")

        # Human-in-the-loop permission check
        allowed, reason = self.permission_guard.check_permission(tool_name, args)
        if not allowed:
            ui.print_warning(f"Permission denied for '{tool_name}': {reason}")
            return ToolResult(
                success=False,
                output="",
                error=f"User denied permission to run {tool_name}. Reason: {reason}",
            )

        # Show tool running badge in UI
        args_summary = ", ".join(f"{k}={repr(v)[:30]}" for k, v in args.items())
        ui.print_tool_start(tool_name, args_summary)

        try:
            import inspect
            exec_fn = tool.execute
            if inspect.iscoroutinefunction(exec_fn):
                result = await exec_fn(**args)
            else:
                result = exec_fn(**args)
                if inspect.iscoroutine(result):
                    result = await result

            if not isinstance(result, ToolResult):
                if isinstance(result, dict):
                    result = ToolResult(
                        success=result.get("success", True),
                        output=json.dumps(result, ensure_ascii=False) if not result.get("output") else str(result.get("output")),
                        error=result.get("error"),
                    )
                else:
                    result = ToolResult(success=True, output=str(result))

            snippet = result.output or result.error or ""
            ui.print_tool_result(tool_name, success=result.success, snippet=snippet)
            return result
        except Exception as e:
            err_msg = f"Exception in tool '{tool_name}': {e}"
            ui.print_error(err_msg)
            return ToolResult(success=False, output="", error=err_msg)
