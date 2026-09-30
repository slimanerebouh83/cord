"""
Tests for tool call streaming collision prevention and robust multi-call indexing.
Verifies that when a model outputs multiple tool calls (or pseudo-reasoning tools)
sharing index 0, they are never concatenated into corrupt names like 'thinkwrite_file'.
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from cord.core.agent import CordAgent
from cord.core.config import CordConfig
from cord.core.permissions import PermissionGuard
from cord.core.llm import StreamChunk, ToolCallDelta
from cord.tools.registry import ToolRegistry
from cord.tools.filesystem.write_file import WriteFileTool


@pytest.mark.asyncio
async def test_agent_accumulates_distinct_tools_without_merging(tmp_path):
    config = CordConfig(provider="gemini", model="gemini-3.5-flash-lite", permission_mode="yolo", workspace_dir=str(tmp_path))
    guard = PermissionGuard(config)
    registry = ToolRegistry(guard)
    registry.register(WriteFileTool())

    agent = CordAgent(config=config, tool_registry=registry)

    calc_file = str(tmp_path / "calc.py")
    chunks = [
        StreamChunk(
            tool_call_delta=ToolCallDelta(
                index=0,
                id="call_think_1",
                name="think",
                arguments='{"thought": "analyzing calculation requirements"}',
            )
        ),
        StreamChunk(
            tool_call_delta=ToolCallDelta(
                index=0,
                id="call_write_2",
                name="write_file",
                arguments=json.dumps({"path": calc_file, "content": "print(42)"}),
            )
        ),
    ]

    # Spy on execute_single_tool
    tool_names_called = []
    original_exec = registry.execute

    async def spy_exec(name, args, **kwargs):
        tool_names_called.append(name)
        return await original_exec(name, args, **kwargs)

    registry.execute = spy_exec

    turns = [
        # turn 1
        lambda: (c for c in chunks),
        # turn 2
        lambda: (c for c in [StreamChunk(text="Calculator created.")]),
    ]

    async def mock_stream_turn_1(*args, **kwargs):
        for c in chunks:
            yield c

    async def mock_stream_turn_2(*args, **kwargs):
        yield StreamChunk(text="Calculator created.")

    stream_turns = [mock_stream_turn_1(), mock_stream_turn_2()]
    with patch.object(agent.llm, "stream_chat", side_effect=lambda *a, **k: stream_turns.pop(0)):
        res = await agent.step("اصنع الة حاسبة وافتحها لي")
    # Verify thinkwrite_file was NEVER formed or called!
    assert "thinkwrite_file" not in tool_names_called
    # And write_file was called
    assert "write_file" in tool_names_called
    # And file was written
    with open(calc_file, "r") as f:
        assert f.read() == "print(42)"
