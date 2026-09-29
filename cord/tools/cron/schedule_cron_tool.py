"""
CORD Tools - Schedule Recurring Automation Job Tool
Registers recurring tasks like 'every morning at 8:00', 'every 24h', or cron expressions.
"""

from __future__ import annotations
import time
from typing import Optional
from cord.tools.base import BaseTool, ToolResult
from cord.cron.cron_manager import cron_mgr


class ScheduleCronJobTool(BaseTool):
    name = "cron_schedule"
    description = (
        "Schedules an autonomous recurring task that runs automatically in the background. "
        "Supports natural language intervals ('every morning at 8:00', 'every 24h', 'every 30m') "
        "or standard cron expressions ('0 8 * * *'). Can target the local system or remote fleet machines."
    )
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Descriptive name for the scheduled job (e.g. 'Daily AI News Digest')"},
            "schedule": {
                "type": "string",
                "description": "Recurrence expression (e.g. 'every morning at 8:00', 'every 24h', 'every 1h', '0 8 * * *')",
            },
            "prompt": {
                "type": "string",
                "description": "Task instructions for the agent to execute (e.g. 'Search for the latest AI news in the past 24h, generate a Word docx report, and email it to me')",
            },
            "target_node": {
                "type": "string",
                "description": "Machine to execute on: 'local' (default) or the name of a registered fleet machine",
                "default": "local",
            },
            "action_type": {
                "type": "string",
                "enum": ["agent_prompt", "generate_report", "send_email", "sync_files"],
                "description": "Type of action to perform",
                "default": "agent_prompt",
            },
            "recipient_email": {
                "type": "string",
                "description": "Optional email address to send the completed report/alert to",
            },
            "output_path": {
                "type": "string",
                "description": "Optional path for output file (e.g. 'daily_ai_briefing.docx')",
            },
        },
        "required": ["name", "schedule", "prompt"],
    }

    async def execute(
        self,
        name: str,
        schedule: str,
        prompt: str,
        target_node: str = "local",
        action_type: str = "agent_prompt",
        recipient_email: Optional[str] = None,
        output_path: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        job = cron_mgr.add_job(
            name=name,
            schedule_expr=schedule,
            prompt=prompt,
            target_node=target_node,
            action_type=action_type,
            recipient_email=recipient_email,
            output_path=output_path,
        )

        next_time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(job.next_run))
        return ToolResult(
            success=True,
            output=(
                f"✔ Scheduled recurring task '{job.name}' (ID: {job.id})\n"
                f"- Schedule: {job.schedule_expr}\n"
                f"- Target Machine: {job.target_node}\n"
                f"- Action: {job.action_type}\n"
                f"- Next Run: {next_time_str}\n"
                f"- Instructions: {job.prompt}"
            ),
        )
