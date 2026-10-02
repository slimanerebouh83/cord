"""
CORD Tools - Community Sentinel Triage Tool
Allows agents to triage community suggestions, bug reports, and RFCs using multi-agent deliberation.
"""

from __future__ import annotations
import json
from typing import Dict, Any, Optional
from cord.tools.base import BaseTool, ToolResult, PermissionLevel, RiskLevel
from cord.subagents.sentinel import community_sentinel


class SentinelTriageTool(BaseTool):
    """Triages a community suggestion, GitHub issue, or feature idea via the Sentinel Council."""

    name = "sentinel_triage"
    description = (
        "Submit a community proposal, feature request, or bug report to the autonomous Sentinel Council. "
        "The multi-agent council deliberates across Architecture, Security, Developer Experience, and QA "
        "to deliver a binding consensus verdict and RFC action plan."
    )
    parameters = {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Short title of the proposal or issue.",
            },
            "description": {
                "type": "string",
                "description": "Comprehensive description of the suggestion, proposed change, or reported problem.",
            },
            "category": {
                "type": "string",
                "enum": ["feature_request", "bug_report", "rfc", "enhancement"],
                "description": "Category of the proposal.",
            },
            "author": {
                "type": "string",
                "description": "Author or source of the proposal (e.g. 'github:@username' or 'community').",
            },
        },
        "required": ["title", "description"],
    }
    required_permission = PermissionLevel.EXECUTE
    risk_level = RiskLevel.LOW

    async def execute(
        self,
        title: str,
        description: str,
        category: str = "feature_request",
        author: str = "community",
    ) -> ToolResult:
        try:
            res = await community_sentinel.triage_proposal(
                title=title,
                description=description,
                category=category,
                author=author,
            )
            return ToolResult(
                success=True,
                output=json.dumps(res, indent=2),
                metadata=res,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Sentinel triage failed: {e}",
            )
