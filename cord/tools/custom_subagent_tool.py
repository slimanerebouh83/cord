"""
CORD Tools - Dynamic AI Subagent Creation Tool
Empowers the AI to autonomously invent, configure, and spawn specialized subagents on the fly.
Custom subagents inherit the parent agent's active provider, model, and configuration by default.
"""

from __future__ import annotations
from typing import List, Optional

from cord.tools.base import BaseTool, ToolResult
from cord.subagents.manager import SubagentManager


class CreateCustomSubagentTool(BaseTool):
    name = "create_custom_subagent"
    description = (
        "Autonomously define and spawn a custom specialized subagent on the fly. "
        "You provide the custom role name, detailed system prompt instructions, specific tools allowed, and the task. "
        "The subagent executes using the parent agent's active provider/model (or custom overrides) in an isolated loop and returns a comprehensive report."
    )
    parameters = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Short snake_case name for the subagent (e.g. 'sql_optimizer', 'api_architect', 'security_auditor').",
            },
            "role_title": {
                "type": "string",
                "description": "Human-readable role title (e.g. 'SQL Performance Specialist').",
            },
            "system_prompt": {
                "type": "string",
                "description": "Tailored, highly specific system prompt defining the subagent's expertise and guidelines.",
            },
            "tools": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of tool names to grant this subagent (e.g. ['read_file', 'write_file', 'edit_file', 'search_files', 'execute_command']).",
            },
            "task": {
                "type": "string",
                "description": "Detailed task instructions for the subagent to execute.",
            },
            "model": {
                "type": "string",
                "description": "Optional model override. Defaults to inheriting the spawning agent's active model.",
            },
            "provider": {
                "type": "string",
                "description": "Optional provider override. Defaults to inheriting the spawning agent's active provider.",
            },
        },
        "required": ["name", "role_title", "system_prompt", "tools", "task"],
    }

    def __init__(self, manager: SubagentManager):
        self.manager = manager

    async def execute(
        self,
        name: str,
        role_title: str,
        system_prompt: str,
        tools: List[str],
        task: str,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        try:
            res = await self.manager.spawn_custom(
                name=name,
                role_title=role_title,
                system_prompt=system_prompt,
                tool_names=tools,
                task=task,
                model=model,
                provider=provider,
            )
            output = f"Custom Subagent [{res.role.upper()}] Execution Report:\n"
            output += f"Provider / Model: {res.provider} / {res.model}\n"
            output += f"Status: {'Success' if res.success else 'Failed'}\n"
            output += f"Tool calls executed: {res.tool_calls_count}\n"
            output += f"Findings & Results:\n{res.summary}"
            return ToolResult(success=res.success, output=output, metadata={"details": res.details})
        except Exception as e:
            return ToolResult(success=False, output="", error=f"Failed to execute custom subagent: {e}")
