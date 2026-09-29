"""
Tests for Collaborative Subagent Planning, Deliberation, and Background Tool Execution.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from cord.core.config import CordConfig
from cord.core.agent import CordAgent
from cord.core.permissions import PermissionGuard
from cord.tools.registry import ToolRegistry
from cord.tools.shell.execute_command import ExecuteCommandTool
from cord.tools.process.manage_process import ManageProcessTool
from cord.execution.process_tracker import process_tracker
from cord.subagents.manager import SubagentManager
from cord.subagents.base_subagent import SubagentResult
from cord.subagents.collaborative_planner import CollaborativePlanner
from cord.tools.subagents.collaborative_plan_tool import CollaborativePlanTool
from cord.tools.subagents.subagent_deliberate_tool import SubagentDeliberateTool
from cord.tools.subagents.run_parallel_subagents_tool import RunParallelSubagentsTool
from cord.tools.filesystem.read_file import ReadFileTool


@pytest.mark.asyncio
async def test_execute_command_background_and_manage_process(tmp_path):
    """Verifies that execute_command can run in the background and manage_process can inspect it."""
    cmd_tool = ExecuteCommandTool()
    manage_tool = ManageProcessTool()

    # Launch a quick non-blocking background command
    res = await cmd_tool.execute(
        command="python -c \"import time; print('hello background'); time.sleep(0.5); print('done background')\"",
        cwd=str(tmp_path),
        is_background=True,
    )

    assert res.success is True
    assert "Background command started" in res.output
    proc_id = res.metadata.get("proc_id")
    assert proc_id is not None
    assert proc_id.startswith("proc_")

    # Verify manage_process can list active processes
    list_res = await manage_tool.execute(action="list")
    assert list_res.success is True
    assert proc_id in list_res.output

    # Wait briefly for process to write output
    await asyncio.sleep(0.7)

    # Inspect logs
    logs_res = await manage_tool.execute(action="logs", proc_id=proc_id)
    assert logs_res.success is True
    assert "hello background" in logs_res.output or "done background" in logs_res.output or "terminated" in logs_res.output


@pytest.mark.asyncio
async def test_subagent_deliberation_and_consensus():
    """Verifies that SubagentDeliberateTool enables peer voting and computes mathematical consensus."""
    delib_tool = SubagentDeliberateTool()
    res = await delib_tool.execute(
        topic="Database Storage Strategy",
        options=["PostgreSQL Relational Storage", "MongoDB Document Store", "SQLite Embedded"],
        voters=["researcher", "coder", "reviewer"],
    )

    assert res.success is True
    assert "Deliberation Concluded" in res.output
    assert "Consensus Reached: YES" in res.output
    assert "Winning Strategy: PostgreSQL Relational Storage" in res.output
    assert "Peer Arguments" in res.output


@pytest.mark.asyncio
async def test_collaborative_planner_synthesis_and_execution(tmp_path):
    """Verifies CollaborativePlanner automatically decomposes goals and executes phases."""
    cfg = CordConfig(workspace_dir=str(tmp_path))
    guard = PermissionGuard(cfg)
    registry = ToolRegistry(guard)
    manager = SubagentManager(config=cfg, available_tools=registry.tools)

    planner = CollaborativePlanner(manager)
    phases = planner.synthesize_plan("Build User Authentication with JWT")

    assert len(phases) == 5
    assert phases[0].role == "researcher"
    assert phases[1].role == "coder"
    assert phases[1].deliberation_topic is not None
    assert phases[2].role == "coder"
    assert phases[3].role == "reviewer"
    assert phases[4].role == "tester"

    # Mock manager.spawn to simulate successful subagent execution
    with patch.object(manager, "spawn", new_callable=AsyncMock) as mock_spawn:
        mock_spawn.return_value = SubagentResult(
            role="collaborator",
            task="Completed phase",
            success=True,
            summary="Phase objectives thoroughly met.",
            tool_calls_count=2,
            model=cfg.model,
            provider=cfg.provider,
        )

        plan_tool = CollaborativePlanTool(subagent_manager=manager)
        res = await plan_tool.execute(goal="Build User Authentication with JWT")

        assert res.success is True
        assert "Collaborative Plan Execution: SUCCESS" in res.output
        assert "Phases Completed: 5/5" in res.output


@pytest.mark.asyncio
async def test_run_parallel_subagents(tmp_path):
    """Verifies RunParallelSubagentsTool runs multiple subagents simultaneously."""
    cfg = CordConfig(workspace_dir=str(tmp_path))
    guard = PermissionGuard(cfg)
    registry = ToolRegistry(guard)
    manager = SubagentManager(config=cfg, available_tools=registry.tools)

    with patch.object(manager, "spawn", new_callable=AsyncMock) as mock_spawn:
        mock_spawn.side_effect = [
            SubagentResult(role="researcher", task="Research API", success=True, summary="API documented", tool_calls_count=1),
            SubagentResult(role="coder", task="Implement endpoints", success=True, summary="Endpoints coded", tool_calls_count=2),
            SubagentResult(role="tester", task="Verify tests", success=True, summary="Tests passing", tool_calls_count=1),
        ]

        parallel_tool = RunParallelSubagentsTool(manager=manager)
        res = await parallel_tool.execute(
            tasks=[
                {"role": "researcher", "task": "Research API"},
                {"role": "coder", "task": "Implement endpoints"},
                {"role": "tester", "task": "Verify tests"},
            ],
            max_concurrency=3,
        )

        assert res.success is True
        assert "Total Subagents Dispatched: 3" in res.output
        assert "RESEARCHER" in res.output
        assert "CODER" in res.output
        assert "TESTER" in res.output


@pytest.mark.asyncio
async def test_agent_parallel_tool_calling(tmp_path):
    """Verifies that CordAgent executes multiple independent tool calls in parallel."""
    cfg = CordConfig(workspace_dir=str(tmp_path))
    guard = PermissionGuard(cfg)
    registry = ToolRegistry(guard)
    registry.register(ReadFileTool())

    # Create 2 test files
    f1 = tmp_path / "f1.txt"
    f2 = tmp_path / "f2.txt"
    f1.write_text("content 1", encoding="utf-8")
    f2.write_text("content 2", encoding="utf-8")

    agent = CordAgent(config=cfg, tool_registry=registry)

    # Mock stream_chat to return 2 parallel read_file calls on turn 1, and text on turn 2
    from cord.core.llm import StreamChunk, ToolCallDelta

    turn = 0

    async def mock_stream(*args, **kwargs):
        nonlocal turn
        turn += 1
        if turn == 1:
            yield StreamChunk(
                tool_call_delta=ToolCallDelta(
                    index=0,
                    id="call_f1",
                    name="read_file",
                    arguments=f'{{"path": "{str(f1).replace(chr(92), "/")}"}}',
                )
            )
            yield StreamChunk(
                tool_call_delta=ToolCallDelta(
                    index=1,
                    id="call_f2",
                    name="read_file",
                    arguments=f'{{"path": "{str(f2).replace(chr(92), "/")}"}}',
                )
            )
        else:
            yield StreamChunk(text="Both files read successfully.")

    agent.llm.stream_chat = mock_stream
    response = await agent.step("Read both f1 and f2 in parallel")

    assert "Both files read successfully." in response
    # Verify tool results were recorded in messages in order
    tool_messages = [m for m in agent.messages if m.get("role") == "tool"]
    assert len(tool_messages) == 2
    assert "content 1" in tool_messages[0]["content"]
    assert "content 2" in tool_messages[1]["content"]
