"""CORD Tools - Concurrent Multi-Subagent Parallel Dispatch Tool"""
from __future__ import annotations
import asyncio
from typing import Optional, List, Dict, Any
from cord.tools.base import BaseTool, ToolResult, PermissionLevel, RiskLevel
from cord.subagents.base_subagent import SubagentResult


class RunParallelSubagentsTool(BaseTool):
    name = "run_parallel_subagents"
    description = (
        "Spawns and executes multiple specialized subagents concurrently in parallel. "
        "Each subagent runs in an isolated loop with its own role, task instructions, and tools, "
        "returning all aggregated results simultaneously without serial delays."
    )
    required_permission = PermissionLevel.EXECUTE
    risk_level = RiskLevel.MEDIUM

    parameters = {
        "type": "object",
        "properties": {
            "tasks": {
                "type": "array",
                "description": "List of subagent assignments to run in parallel.",
                "items": {
                    "type": "object",
                    "properties": {
                        "role": {
                            "type": "string",
                            "enum": ["researcher", "coder", "reviewer", "tester"],
                            "description": "Specialized role for this worker.",
                        },
                        "task": {
                            "type": "string",
                            "description": "Detailed task instructions for this subagent.",
                        },
                        "name": {
                            "type": "string",
                            "description": "Optional custom name for this subagent.",
                        },
                        "model": {
                            "type": "string",
                            "description": "Optional model override (inherits parent model by default).",
                        },
                    },
                    "required": ["role", "task"],
                },
            },
            "max_concurrency": {
                "type": "integer",
                "description": "Maximum concurrent subagents executing at the same time (default 5).",
                "default": 5,
            },
        },
        "required": ["tasks"],
    }

    def __init__(self, manager: Any):
        super().__init__()
        self.manager = manager

    async def execute(
        self,
        tasks: List[Dict[str, Any]],
        max_concurrency: int = 5,
        **kwargs,
    ) -> ToolResult:
        if not tasks:
            return ToolResult(success=False, output="", error="No subagent tasks provided.")

        sem = asyncio.Semaphore(max(1, max_concurrency))

        async def _run_one(t_item: Dict[str, Any]) -> SubagentResult:
            role = t_item.get("role", "coder")
            task_desc = t_item.get("task", "")
            c_name = t_item.get("name")
            mod = t_item.get("model")

            async with sem:
                return await self.manager.spawn(
                    role=role,
                    task=task_desc,
                    custom_name=c_name,
                    model=mod,
                )

        coros = [_run_one(t) for t in tasks]
        results: List[SubagentResult] = await asyncio.gather(*coros)

        all_success = all(r.success for r in results)
        output_lines = [
            f"Parallel Subagents Execution: {'SUCCESS ✓' if all_success else 'COMPLETED WITH WARNINGS'}",
            f"Total Subagents Dispatched: {len(results)}",
            "",
            "Subagent Reports:",
        ]

        for i, r in enumerate(results, 1):
            st = "✓" if r.success else "✖"
            output_lines.append(f"[{i}] [{st}] [{r.role.upper()}] ({r.provider}/{r.model}) - Tools used: {r.tool_calls_count}")
            output_lines.append(f"    Summary: {r.summary[:200]}")

        return ToolResult(
            success=all_success,
            output="\n".join(output_lines),
            metadata={"total": len(results), "success_count": sum(1 for r in results if r.success)},
        )
