"""
CORD Tools - Tech Radar & MCP Marketplace Tool
Enables autonomous agents to discover frontier AI capabilities and configure MCP servers.
"""

from __future__ import annotations
import json
from typing import Dict, Any, Optional
from cord.tools.base import BaseTool, ToolResult, PermissionLevel, RiskLevel
from cord.core.tech_radar import tech_radar, MCP_MARKETPLACE, FRONTIER_MODELS


class TechRadarTool(BaseTool):
    """Explores frontier models and manages MCP server marketplace installations."""

    name = "tech_radar"
    description = (
        "Inspect the Internet Tech Radar for frontier AI models (benchmarks, context windows) "
        "and curated MCP servers. Can list available servers or install an MCP server into the project."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["overview", "list_mcp", "install_mcp", "list_models"],
                "description": "Action to perform: 'overview', 'list_mcp', 'install_mcp', or 'list_models'.",
            },
            "server_key": {
                "type": "string",
                "description": "The MCP server key to install (required if action is 'install_mcp', e.g. 'github', 'postgres', 'brave-search').",
            },
        },
        "required": ["action"],
    }
    required_permission = PermissionLevel.EXECUTE
    risk_level = RiskLevel.LOW

    async def execute(self, action: str = "overview", server_key: Optional[str] = None) -> ToolResult:
        try:
            if action == "install_mcp":
                if not server_key:
                    return ToolResult(success=False, output="", error="server_key is required for install_mcp action.")
                res = tech_radar.install_mcp_server(server_key)
                return ToolResult(
                    success=res["success"],
                    output=res.get("message", res.get("error", "")),
                    error=res.get("error") if not res["success"] else None,
                )

            elif action == "list_mcp":
                return ToolResult(
                    success=True,
                    output=json.dumps(MCP_MARKETPLACE, indent=2),
                )

            elif action == "list_models":
                return ToolResult(
                    success=True,
                    output=json.dumps(FRONTIER_MODELS, indent=2),
                )

            else:
                tech_radar.render_radar()
                return ToolResult(
                    success=True,
                    output="Rendered Tech Radar overview.",
                )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Tech radar failed: {e}",
            )
