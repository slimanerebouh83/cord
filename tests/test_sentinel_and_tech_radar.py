"""
Tests for Community Sentinel Multi-Agent Council and Internet Tech Radar.
"""

import pytest
from pathlib import Path
from cord.subagents.sentinel import CommunitySentinel
from cord.tools.sentinel_tool import SentinelTriageTool
from cord.core.tech_radar import InternetTechRadar, MCP_MARKETPLACE
from cord.tools.tech_radar_tool import TechRadarTool


@pytest.mark.asyncio
async def test_sentinel_multi_agent_council_triage(tmp_path):
    """Verifies that CommunitySentinel runs a 4-role deliberation council and reaches consensus."""
    sentinel = CommunitySentinel(storage_dir=tmp_path / "sentinel")

    verdict = await sentinel.triage_proposal(
        title="Add AST Call-Graph Visualizer",
        description="Add an in-memory AST call-graph visualizer to predict test impact before code modifications.",
        category="feature_request",
        author="@contributor-alice",
    )

    assert "proposal_id" in verdict
    assert verdict["status"] in ("accepted", "accepted_refined", "deferred", "rejected")
    assert verdict["consensus_percentage"] > 0
    assert "Council voted with" in verdict["rfc_summary"]
    assert len(sentinel.proposals) >= 1


@pytest.mark.asyncio
async def test_sentinel_triage_tool_execution(tmp_path, monkeypatch):
    """Verifies that SentinelTriageTool executes cleanly and returns structured metadata."""
    from cord.subagents.sentinel import community_sentinel
    monkeypatch.setattr(community_sentinel, "storage_dir", tmp_path / "sentinel")
    community_sentinel.proposals.clear()

    tool = SentinelTriageTool()
    res = await tool.execute(
        title="Fix memory leak in background subagents",
        description="Subagent processes should be garbage-collected immediately when completed.",
        category="bug_report",
    )

    assert res.success is True
    assert "proposal_id" in res.metadata
    assert res.metadata["status"] in ("accepted", "accepted_refined")


@pytest.mark.asyncio
async def test_tech_radar_mcp_installation(tmp_path):
    """Verifies that InternetTechRadar correctly writes and manages MCP server configs."""
    cfg_file = tmp_path / "mcp_servers.json"
    radar = InternetTechRadar(config_path=cfg_file)

    # Test unknown server
    err_res = radar.install_mcp_server("nonexistent-tool")
    assert err_res["success"] is False

    # Test install github server
    ok_res = radar.install_mcp_server("github")
    assert ok_res["success"] is True
    assert cfg_file.exists()

    # Tool execution
    tool = TechRadarTool()
    tool_res = await tool.execute(action="list_mcp")
    assert tool_res.success is True
    assert "github" in tool_res.output
    assert "postgres" in tool_res.output
