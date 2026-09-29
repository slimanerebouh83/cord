"""
CORD Tools - Delete Scheduled Job Tool
Removes a recurring automation task by ID.
"""

from __future__ import annotations
from cord.tools.base import BaseTool, ToolResult
from cord.cron.cron_manager import cron_mgr


class DeleteCronJobTool(BaseTool):
    name = "cron_delete"
    description = "Removes a scheduled recurring task from the persistent scheduler by its job ID."
    parameters = {
        "type": "object",
        "properties": {
            "job_id": {
                "type": "string",
                "description": "ID of the job to delete (e.g. 'job-a1b2c3')",
            },
        },
        "required": ["job_id"],
    }

    async def execute(self, job_id: str, **kwargs) -> ToolResult:
        removed = cron_mgr.remove_job(job_id.strip())
        if removed:
            return ToolResult(success=True, output=f"✔ Scheduled task '{job_id}' successfully removed.")
        return ToolResult(success=False, output=f"❌ Scheduled task '{job_id}' not found.")
