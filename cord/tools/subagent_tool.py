"""
CORD Tools - Subagent Delegation Tool
Allows the main agent to delegate complex subtasks to specialized subagents.
Subagents inherit the parent agent's active provider, model, and configuration by default.
"""

from __future__ import annotations
from typing import Optional

from cord.tools.base import BaseTool, ToolResult
from cord.subagents.manager import SubagentManager


class SpawnSubagentTool(BaseTool):
    name = "spawn_subagent"
    description = (
        "Delegate a task to an autonomous specialized subagent (researcher, coder, reviewer, tester). "
        "The subagent will autonomously execute the task using the same provider and model as the spawning agent (or custom override) in an isolated context and return a structured summary."
    )
    parameters = {
        "type": "object",
        "properties": {
            "role": {
                "type": "string",
                "enum": ["researcher", "coder", "reviewer", "tester"],
                "description": "The specialized role of the subagent to spawn.",
            },
            "task": {
                "type": "string",
                "description": "Specific, actionable task description for the subagent.",
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
        "required": ["role", "task"],
    }

    def __init__(self, manager: SubagentManager):
        self.manager = manager

    async def execute(
        self,
        role: str,
        task: str,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        try:
            res = await self.manager.spawn(
                role=role,
                task=task,
                model=model,
                provider=provider,
            )
            output = f"Subagent [{res.role.upper()}] Report:\n"
            output += f"Provider / Model: {res.provider} / {res.model}\n"
            output += f"Status: {'Success' if res.success else 'Failed'}\n"
            output += f"Tool calls made: {res.tool_calls_count}\n"
            output += f"Findings / Summary:\n{res.summary}"
            return ToolResult(success=res.success, output=output, metadata={"details": res.details})
        except Exception as e:
            return ToolResult(success=False, output="", error=f"Failed to spawn subagent: {e}")
