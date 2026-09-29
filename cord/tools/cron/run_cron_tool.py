"""
CORD Tools - Run Scheduled Job Now Tool
Triggers immediate execution of a scheduled recurring task.
"""

from __future__ import annotations
from cord.tools.base import BaseTool, ToolResult
from cord.cron.cron_manager import cron_mgr


class RunCronJobNowTool(BaseTool):
    name = "cron_run_now"
    description = "Immediately triggers execution of a scheduled recurring task without waiting for its scheduled time."
    parameters = {
        "type": "object",
        "properties": {
            "job_id": {"type": "string", "description": "ID of the job to execute immediately"},
        },
        "required": ["job_id"],
    }

    async def execute(self, job_id: str, **kwargs) -> ToolResult:
        res = await cron_mgr.execute_job(job_id.strip())
        if res.get("success"):
            return ToolResult(
                success=True,
                output=(
                    f"✔ Executed scheduled task '{res['name']}' in {res.get('duration_s', 0):.2f}s.\n"
                    f"Result Summary:\n{res.get('output')}\n"
                    f"Next scheduled run: {res.get('next_run')}"
                ),
            )
        return ToolResult(
            success=False,
            output=f"❌ Failed executing task '{job_id}': {res.get('error') or res.get('output')}",
        )
