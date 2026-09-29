"""
CORD Tools - List Scheduled Automation Jobs Tool
Inspects all active cron jobs, run history, and next scheduled execution times.
"""

from __future__ import annotations
import time
from cord.tools.base import BaseTool, ToolResult
from cord.cron.cron_manager import cron_mgr


class ListCronJobsTool(BaseTool):
    name = "cron_list"
    description = "Lists all registered recurring background tasks, their recurrence schedules, statuses, and next run times."
    parameters = {"type": "object", "properties": {}}

    async def execute(self, **kwargs) -> ToolResult:
        jobs = cron_mgr.list_jobs()
        if not jobs:
            return ToolResult(
                success=True,
                output="No recurring background tasks scheduled yet. Use cron_schedule to create a task.",
            )

        lines = [f"Found {len(jobs)} scheduled background task(s):"]
        for j in jobs:
            status_icon = "🟢" if j.enabled else "⏸️"
            next_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(j.next_run)) if j.next_run else "N/A"
            last_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(j.last_run)) if j.last_run else "Never"
            lines.append(
                f"- {status_icon} [{j.id}] [bold]{j.name}[/bold] ({j.schedule_expr})\n"
                f"  Target: {j.target_node} │ Runs: {j.run_count} │ Last: {last_str} ({j.last_status}) │ Next: {next_str}\n"
                f"  Prompt: {j.prompt[:80]}..."
            )

        return ToolResult(success=True, output="\n".join(lines))
