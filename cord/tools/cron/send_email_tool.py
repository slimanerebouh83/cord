"""
CORD Tools - Send Email Tool
Dispatches emails with attachments (Word docx, PDFs, markdown) via SMTP or queues them in the local outbox.
"""

from __future__ import annotations
from typing import List, Optional
from cord.tools.base import BaseTool, ToolResult
from cord.cron.email_notifier import email_notifier


class SendEmailTool(BaseTool):
    name = "send_email"
    description = (
        "Sends an automated email notification with optional attachments (Word documents, markdown files). "
        "Uses configured SMTP settings in ~/.cord/email.json or queues the message safely in ~/.cord/outbox."
    )
    parameters = {
        "type": "object",
        "properties": {
            "to": {"type": "string", "description": "Recipient email address"},
            "subject": {"type": "string", "description": "Email subject line"},
            "body": {"type": "string", "description": "Email body content in plain text or markdown"},
            "attachments": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional list of file paths to attach (e.g. ['reports/ai_news.docx'])",
            },
        },
        "required": ["to", "subject", "body"],
    }

    async def execute(
        self,
        to: str,
        subject: str,
        body: str,
        attachments: Optional[List[str]] = None,
        **kwargs,
    ) -> ToolResult:
        res = email_notifier.send(
            to_email=to,
            subject=subject,
            body_text=body,
            attachments=attachments,
        )
        return ToolResult(
            success=res.get("success", True),
            output=res.get("message") or res.get("warning") or str(res),
        )
