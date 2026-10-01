"""
CORD Tools - Dynamic Runtime Tool Creation Engine.
Enables any agent, subagent, or autonomous AI worker to dynamically write, compile,
and register custom executable tools on the fly. Persists tools in ~/.cord/dynamic_tools/.
"""

from __future__ import annotations
import os
import sys
import ast
import json
import inspect
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable

from cord.tools.base import BaseTool, ToolResult
from cord.permissions.levels import PermissionLevel, RiskLevel


class DynamicTool(BaseTool):
    """An executable tool synthesized at runtime by an autonomous agent."""

    def __init__(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        python_code: str,
        func: Callable,
        is_async: bool = True,
        author: str = "agent",
    ):
        super().__init__()
        self.name = name
        self.description = description
        self.parameters = parameters or {"type": "object", "properties": {}, "required": []}
        self.python_code = python_code
        self._func = func
        self._is_async = is_async
        self.author = author
        self.required_permission = PermissionLevel.EXECUTE
        self.risk_level = RiskLevel.MEDIUM

    async def execute(self, **kwargs) -> ToolResult:
        try:
            if self._is_async:
                res = await self._func(**kwargs)
            else:
                res = self._func(**kwargs)

            if isinstance(res, ToolResult):
                return res
            if isinstance(res, dict):
                return ToolResult(success=True, output=json.dumps(res, indent=2, ensure_ascii=False))
        except Exception as e:
            err_msg = f"Dynamic tool '{self.name}' error ({type(e).__name__}): {e}"
            dynamic_tool_manager.record_tool_error(self.name, f"{type(e).__name__}: {e}")
            tip = f"\n💡 Tip: You can fix this tool anytime using `repair_dynamic_tool(name='{self.name}', python_code='...')`"
            return ToolResult(success=False, output="", error=err_msg + tip)


class DynamicToolManager:
    """Manages compilation, registration, execution, and persistence of dynamic tools."""

    def __init__(self, storage_dir: Optional[Path] = None):
        self.storage_dir = storage_dir or (Path.home() / ".cord" / "dynamic_tools")
        self.tools: Dict[str, DynamicTool] = {}
        self.tool_errors: Dict[str, str] = {}
        self._load_persisted_tools()

    def _load_persisted_tools(self) -> None:
        """Loads all dynamic tools saved in ~/.cord/dynamic_tools/."""
        try:
            if not self.storage_dir.exists():
                return
            for file in self.storage_dir.glob("*.json"):
                try:
                    data = json.loads(file.read_text(encoding="utf-8"))
                    name = data.get("name")
                    desc = data.get("description", "Dynamic runtime tool")
                    params = data.get("parameters", {})
                    code = data.get("python_code", "")
                    author = data.get("author", "agent")
                    if name and code:
                        self.compile_and_register(name, desc, params, code, author=author, persist=False)
                except Exception:
                    pass
        except Exception:
            pass

    def compile_and_register(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        python_code: str,
        author: str = "agent",
        persist: bool = True,
    ) -> DynamicTool:
        """Compiles Python code, verifies executable entrypoint, and registers the tool."""
        clean_name = name.strip().lower().replace(" ", "_").replace("-", "_")
        if not clean_name:
            raise ValueError("Tool name must not be empty.")

        # 1. Syntax check
        ast.parse(python_code, filename=f"<dynamic_tool:{clean_name}>")

        # 2. Compile and execute into execution namespace
        namespace: Dict[str, Any] = {
            "ToolResult": ToolResult,
            "json": json,
            "asyncio": asyncio,
            "os": os,
            "sys": sys,
            "Path": Path,
        }
        exec(python_code, namespace)

        # 3. Locate entrypoint ('run' or 'execute' or callable matching name)
        target_func = None
        for candidate in ("run", "execute", clean_name):
            if candidate in namespace and callable(namespace[candidate]):
                target_func = namespace[candidate]
                break

        if not target_func:
            # Fallback: take the first user-defined function in namespace
            import types
            for k, v in namespace.items():
                if isinstance(v, (types.FunctionType, types.CoroutineType)) and not k.startswith("_"):
                    target_func = v
                    break

        if not target_func:
            raise ValueError(
                f"Dynamic tool code must define an entrypoint function (e.g. 'async def run(...):' or 'def execute(...):')."
            )

        is_async = inspect.iscoroutinefunction(target_func)

        tool = DynamicTool(
            name=clean_name,
            description=description.strip(),
            parameters=parameters,
            python_code=python_code,
            func=target_func,
            is_async=is_async,
            author=author,
        )

        self.tools[clean_name] = tool

        # 4. Persist to disk
        if persist:
            try:
                self.storage_dir.mkdir(parents=True, exist_ok=True)
                tool_file = self.storage_dir / f"{clean_name}.json"
                export_data = {
                    "name": clean_name,
                    "description": description,
                    "parameters": parameters,
                    "python_code": python_code,
                    "author": author,
                    "is_async": is_async,
                }
                tool_file.write_text(json.dumps(export_data, indent=2), encoding="utf-8")
            except Exception:
                pass

        # 5. Live dispatch to registries if bound
        if hasattr(self, "_tool_registry") and self._tool_registry:
            try:
                self._tool_registry.register(tool)
            except Exception:
                pass
        if hasattr(self, "_subagent_manager") and self._subagent_manager:
            try:
                self._subagent_manager.available_tools[tool.name] = tool
            except Exception:
                pass

        return tool

    def record_tool_error(self, name: str, error: str) -> None:
        self.tool_errors[name.lower().strip()] = error

    def get_tool_error(self, name: str) -> Optional[str]:
        return self.tool_errors.get(name.lower().strip())

    def get_tool(self, name: str) -> Optional[DynamicTool]:
        return self.tools.get(name.lower().strip())

    def bind_registries(self, tool_registry: Any = None, subagent_manager: Any = None) -> None:
        if tool_registry:
            self._tool_registry = tool_registry
        if subagent_manager:
            self._subagent_manager = subagent_manager

    async def repair_and_register(
        self,
        name: str,
        python_code: str,
        description: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        test_args: Optional[Dict[str, Any]] = None,
    ) -> tuple[DynamicTool, Optional[str]]:
        """Repairs and re-compiles an existing dynamic tool, optionally running verification tests."""
        clean_name = name.strip().lower().replace(" ", "_").replace("-", "_")
        existing = self.tools.get(clean_name)
        effective_desc = description or (existing.description if existing else f"Repaired dynamic tool {clean_name}")
        effective_params = parameters or (existing.parameters if existing else {"type": "object", "properties": {}, "required": []})
        author = existing.author if existing else "agent-repair"

        tool = self.compile_and_register(
            name=clean_name,
            description=effective_desc,
            parameters=effective_params,
            python_code=python_code,
            author=author,
            persist=True,
        )

        self.tool_errors.pop(clean_name, None)

        test_result_output = None
        if test_args is not None:
            res = await tool.execute(**test_args)
            if not res.success:
                raise RuntimeError(f"Verification test with arguments {test_args} failed: {res.error}")
            test_result_output = res.output or "Success"

        return tool, test_result_output

    def delete_tool(self, name: str) -> bool:
        clean_name = name.strip().lower()
        deleted = False
        if clean_name in self.tools:
            del self.tools[clean_name]
            deleted = True
        tool_file = self.storage_dir / f"{clean_name}.json"
        if tool_file.exists():
            tool_file.unlink(missing_ok=True)
            deleted = True
        return deleted

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "author": t.author,
                "parameters": t.parameters,
                "last_error": self.tool_errors.get(t.name),
            }
            for t in self.tools.values()
        ]


dynamic_tool_manager = DynamicToolManager()


class CreateDynamicTool(BaseTool):
    name = "create_dynamic_tool"
    description = (
        "Dynamically synthesize and register a brand-new custom tool into CORD and all subagents. "
        "The tool is compiled live, immediately executable, and permanently saved in ~/.cord/dynamic_tools/."
    )
    required_permission = PermissionLevel.MODIFY
    risk_level = RiskLevel.HIGH
    parameters = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Unique identifier for the new tool (e.g. 'extract_api_endpoints', 'calculate_hash')",
            },
            "description": {
                "type": "string",
                "description": "Clear explanation of what the tool does and when agents should use it",
            },
            "parameters": {
                "type": "object",
                "description": "JSON schema definition of the tool parameters (e.g. {'type': 'object', 'properties': {'target_dir': {'type': 'string'}}, 'required': ['target_dir']})",
            },
            "python_code": {
                "type": "string",
                "description": (
                    "Executable Python code containing an entrypoint function 'async def run(...):' or 'def run(...):'. "
                    "Has access to standard libraries and can return strings, dicts, or ToolResult."
                ),
            },
            "author": {
                "type": "string",
                "description": "Name of the agent or subagent creating this tool (default: 'agent')",
            },
        },
        "required": ["name", "description", "python_code"],
    }

    async def execute(
        self,
        name: str,
        description: str,
        python_code: str,
        parameters: Optional[Dict[str, Any]] = None,
        author: str = "agent",
        **kwargs,
    ) -> ToolResult:
        try:
            params = parameters or {"type": "object", "properties": {}, "required": []}
            tool = dynamic_tool_manager.compile_and_register(
                name=name,
                description=description,
                parameters=params,
                python_code=python_code,
                author=author,
                persist=True,
            )
            return ToolResult(
                success=True,
                output=(
                    f"✔ Dynamic Tool '{tool.name}' successfully compiled, registered, and persisted!\n"
                    f"Description: {tool.description}\n"
                    f"Saved at: {dynamic_tool_manager.storage_dir / f'{tool.name}.json'}\n"
                    f"All agents and subagents can now immediately execute '{tool.name}'."
                ),
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=f"Failed to create dynamic tool: {e}")


class ListDynamicTools(BaseTool):
    name = "list_dynamic_tools"
    description = "List all dynamically synthesized tools available in CORD and across the subagent swarm."
    required_permission = PermissionLevel.READ_ONLY
    risk_level = RiskLevel.LOW
    parameters = {"type": "object", "properties": {}, "required": []}

    async def execute(self, **kwargs) -> ToolResult:
        tools = dynamic_tool_manager.list_tools()
        if not tools:
            return ToolResult(
                success=True,
                output="No dynamic tools currently registered. Use 'create_dynamic_tool' to synthesize a custom tool.",
            )
        lines = ["Registered Dynamic Tools:"]
        for t in tools:
            lines.append(f"- **{t['name']}** (by {t['author']}): {t['description']}")
        return ToolResult(success=True, output="\n".join(lines))


class DeleteDynamicTool(BaseTool):
    name = "delete_dynamic_tool"
    description = "Permanently remove a dynamically created tool."
    required_permission = PermissionLevel.MODIFY
    risk_level = RiskLevel.MEDIUM
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Name of the dynamic tool to remove"},
        },
        "required": ["name"],
    }

    async def execute(self, name: str, **kwargs) -> ToolResult:
        success = dynamic_tool_manager.delete_tool(name)
        if success:
            return ToolResult(success=True, output=f"Dynamic tool '{name}' successfully deleted.")
        return ToolResult(success=False, output="", error=f"Dynamic tool '{name}' not found.")


class RepairDynamicTool(BaseTool):
    name = "repair_dynamic_tool"
    description = (
        "Inspect, fix, and re-compile an existing dynamic tool that encountered an error or needs enhancement. "
        "Replaces the tool's implementation live, verifies it with optional test arguments, and updates disk persistence."
    )
    required_permission = PermissionLevel.MODIFY
    risk_level = RiskLevel.HIGH
    parameters = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Name of the dynamic tool to repair",
            },
            "python_code": {
                "type": "string",
                "description": "The corrected and updated Python code for the tool entrypoint.",
            },
            "description": {
                "type": "string",
                "description": "Optional updated explanation of what the tool does.",
            },
            "parameters": {
                "type": "object",
                "description": "Optional updated JSON schema for tool parameters.",
            },
            "test_args": {
                "type": "object",
                "description": "Optional test inputs to execute immediately to verify the repair succeeded.",
            },
        },
        "required": ["name", "python_code"],
    }

    async def execute(
        self,
        name: str,
        python_code: str,
        description: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        test_args: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> ToolResult:
        try:
            tool, test_output = await dynamic_tool_manager.repair_and_register(
                name=name,
                python_code=python_code,
                description=description,
                parameters=parameters,
                test_args=test_args,
            )
            test_msg = f"\n🧪 Verification Test Passed: {test_output}" if test_output else ""
            return ToolResult(
                success=True,
                output=(
                    f"✔ Dynamic Tool '{tool.name}' successfully repaired, recompiled, and verified!{test_msg}\n"
                    f"The updated tool is immediately active and available to all agents."
                ),
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=f"Failed to repair dynamic tool '{name}': {e}")

