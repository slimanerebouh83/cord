"""
CORD Tools - Document & Report Generator Tool (Word .docx & Markdown)
Creates structured Microsoft Word (.docx) documents with headings, paragraphs, tables, and bullet points.
"""

from __future__ import annotations
import os
from typing import List, Dict, Any, Optional
from cord.tools.base import BaseTool, ToolResult
from cord.cron.report_generator import report_generator


class GenerateReportTool(BaseTool):
    name = "generate_report"
    description = (
        "Generates a structured Microsoft Word (.docx) document or Markdown file. "
        "Supports custom titles, subtitles, formatted sections, bullet points, and data tables. "
        "Ideal for generating research briefings, AI news digests, or documentation."
    )
    parameters = {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Document title"},
            "output_path": {
                "type": "string",
                "description": "File output path (e.g. 'reports/daily_ai_briefing.docx' or 'notes.md')",
            },
            "format": {
                "type": "string",
                "enum": ["docx", "markdown"],
                "description": "Output format: 'docx' for Word document, 'markdown' for .md",
                "default": "docx",
            },
            "subtitle": {"type": "string", "description": "Optional subtitle"},
            "sections": {
                "type": "array",
                "description": "List of document sections with 'heading', 'content', 'bullets', or 'table'",
                "items": {
                    "type": "object",
                    "properties": {
                        "heading": {"type": "string"},
                        "content": {"type": "string"},
                        "bullets": {"type": "array", "items": {"type": "string"}},
                        "table": {
                            "type": "object",
                            "properties": {
                                "headers": {"type": "array", "items": {"type": "string"}},
                                "rows": {"type": "array", "items": {"type": "array", "items": {"type": "string"}}},
                            },
                        },
                    },
                },
            },
        },
        "required": ["title", "output_path", "sections"],
    }

    async def execute(
        self,
        title: str,
        output_path: str,
        sections: List[Dict[str, Any]],
        format: str = "docx",
        subtitle: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        try:
            if format.lower() == "docx" or output_path.endswith(".docx"):
                saved_path = report_generator.generate_docx(
                    title=title,
                    sections=sections,
                    output_path=output_path,
                    subtitle=subtitle,
                )
            else:
                saved_path = report_generator.generate_markdown(
                    title=title,
                    sections=sections,
                    output_path=output_path,
                    subtitle=subtitle,
                )

            size_bytes = os.path.getsize(saved_path) if os.path.exists(saved_path) else 0
            return ToolResult(
                success=True,
                output=f"✔ Successfully generated report at '{saved_path}' ({size_bytes:,} bytes).",
            )
        except Exception as e:
            return ToolResult(success=False, output=f"❌ Failed to generate report: {e}")
