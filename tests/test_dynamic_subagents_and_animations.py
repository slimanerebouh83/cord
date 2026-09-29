"""
Tests for Dynamic AI Subagents and Animations Engine.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from cord.core.config import CordConfig
from cord.subagents.manager import SubagentManager
from cord.subagents.base_subagent import SubagentResult
from cord.tools.custom_subagent_tool import CreateCustomSubagentTool
from cord.tools.file_tools import ReadFileTool, WriteFileTool
from cord.ui.animations import ThinkingAnimation, ToolAnimation


@pytest.mark.asyncio
async def test_dynamic_subagent_synthesis(tmp_path):
    cfg = CordConfig(workspace_dir=str(tmp_path))
    tools = {
        "read_file": ReadFileTool(),
        "write_file": WriteFileTool(),
    }
    manager = SubagentManager(config=cfg, available_tools=tools)

    # Mock the subagent run method to simulate subagent completion
    mock_result = SubagentResult(
        role="SQL Performance Specialist",
        task="Optimize SQL queries in app.py",
        success=True,
        summary="Optimized 3 slow database queries and added indexing.",
        tool_calls_count=2,
    )

    with patch("cord.subagents.base_subagent.Subagent.run", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = mock_result

        # Execute custom subagent tool
        custom_tool = CreateCustomSubagentTool(manager=manager)
        tool_res = await custom_tool.execute(
            name="sql_optimizer",
            role_title="SQL Performance Specialist",
            system_prompt="You are an expert database performance engineer.",
            tools=["read_file", "write_file"],
            task="Optimize SQL queries in app.py",
        )

        assert tool_res.success is True
        assert "SQL PERFORMANCE SPECIALIST" in tool_res.output
        assert "Optimized 3 slow database queries" in tool_res.output
        assert "sql_optimizer" in manager.custom_subagents


@pytest.mark.asyncio
async def test_thinking_animation_lifecycle():
    anim = ThinkingAnimation(model_name="test-model")
    await anim.start()
    assert anim._running is True
    # Let it tick for a brief moment
    await asyncio.sleep(0.15)
    await anim.stop()
    assert anim._running is False
    assert anim._task is None


@pytest.mark.asyncio
async def test_tool_animation_lifecycle():
    anim = ToolAnimation(tool_name="test_tool", args_summary="foo=bar")
    await anim.start()
    assert anim._running is True
    await asyncio.sleep(0.1)
    await anim.stop()
    assert anim._running is False
    assert anim._task is None
