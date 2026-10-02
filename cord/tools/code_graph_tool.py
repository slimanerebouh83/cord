"""
CORD Tools - Code Graph & Blast Radius Impact Analyzer Tool
Provides AI agents with AST semantic call-graph inspection and blast radius prediction.
"""

from __future__ import annotations
import json
from typing import Dict, Any, Optional
from cord.tools.base import BaseTool, ToolResult, PermissionLevel, RiskLevel
from cord.core.code_graph import code_graph_engine


class CodeImpactAnalysisTool(BaseTool):
    """Analyzes AST call graphs and blast radius for files or symbols before editing."""

    name = "analyze_code_impact"
    description = (
        "Inspect the project AST semantic code graph to determine the blast radius and potential "
        "regressions before editing a function, class, or file. Returns affected caller sites, "
        "dependent files, and associated unit tests."
    )
    parameters = {
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "description": "The function name, class name, or relative file path to analyze (e.g. 'execute_plan' or 'cord/main.py').",
            },
        },
        "required": ["target"],
    }
    required_permission = PermissionLevel.READ_ONLY
    risk_level = RiskLevel.LOW

    async def execute(self, target: str) -> ToolResult:
        try:
            report = code_graph_engine.analyze_blast_radius(target)
            return ToolResult(
                success=True,
                output=json.dumps(report, indent=2),
                metadata=report,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Failed to analyze blast radius for '{target}': {e}",
            )
