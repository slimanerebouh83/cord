"""
Tests for CORD Agent Execution Loop and Subagents.
"""

import pytest
import json
from unittest.mock import AsyncMock, patch
from cord.core.config import CordConfig
from cord.core.permissions import PermissionGuard
from cord.tools.registry import ToolRegistry
from cord.tools.file_tools import ReadFileTool, WriteFileTool
from cord.core.agent import CordAgent
from cord.core.llm import StreamChunk, ToolCallDelta


@pytest.mark.asyncio
async def test_agent_tool_calling_loop(tmp_path):
    cfg = CordConfig(permission_mode="yolo", workspace_dir=str(tmp_path))
    guard = PermissionGuard(cfg)
    registry = ToolRegistry(guard)
    registry.register(WriteFileTool())
    registry.register(ReadFileTool())

    agent = CordAgent(config=cfg, tool_registry=registry)

    # Mock stream_chat to simulate 1 tool call turn followed by final answer
    async def mock_stream_turn_1(*args, **kwargs):
        # Emits a tool call to write_file
        yield StreamChunk(thinking="I should write the file now.")
        yield StreamChunk(
            tool_call_delta=ToolCallDelta(
                index=0,
                id="call_1",
                name="write_file",
                arguments=json.dumps({"path": str(tmp_path / "greeting.txt"), "content": "Hello from Agent!"}),
            )
        )

    async def mock_stream_turn_2(*args, **kwargs):
        # Emits final response
        yield StreamChunk(text="I have successfully created greeting.txt.")

    turns = [mock_stream_turn_1(), mock_stream_turn_2()]

    with patch.object(agent.llm, "stream_chat", side_effect=lambda *a, **k: turns.pop(0)):
        result = await agent.step("Create a greeting file")

    assert "greeting.txt" in result
    target_file = tmp_path / "greeting.txt"
    assert target_file.exists()
    assert target_file.read_text(encoding="utf-8") == "Hello from Agent!"
