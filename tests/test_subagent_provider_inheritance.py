"""
Tests for Subagent Provider/Model Inheritance, Tool Aliasing, and Resilient Execution.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from cord.core.config import CordConfig
from cord.core.agent import CordAgent
from cord.core.permissions import PermissionGuard
from cord.tools.registry import ToolRegistry
from cord.subagents.manager import SubagentManager
from cord.subagents.base_subagent import Subagent, SubagentResult
from cord.tools.subagent_tool import SpawnSubagentTool
from cord.tools.custom_subagent_tool import CreateCustomSubagentTool
from cord.tools.filesystem.read_file import ReadFileTool
from cord.tools.filesystem.list_directory import ListDirectoryTool
from cord.tools.filesystem.search_files import SearchFilesTool
from cord.tools.shell.execute_command import ExecuteCommandTool


@pytest.mark.asyncio
async def test_subagent_inherits_parent_provider_and_model(tmp_path):
    """Verifies that subagents automatically inherit the exact provider and model of the spawning agent."""
    cfg = CordConfig(
        workspace_dir=str(tmp_path),
        provider="nvidia",
        model="nvidia/nemotron-3-super-120b-a12b",
        base_url="https://integrate.api.nvidia.com/v1",
        api_key="nvapi-testkey-12345",
    )
    guard = PermissionGuard(cfg)
    registry = ToolRegistry(guard)
    registry.register(ReadFileTool())
    registry.register(ListDirectoryTool())

    manager = SubagentManager(config=cfg, available_tools=registry.tools)
    agent = CordAgent(config=cfg, tool_registry=registry, subagent_manager=manager)

    # Check that parent linkage is established
    assert manager.parent_agent is agent
    eff_cfg = manager.get_effective_config()
    assert eff_cfg.provider == "nvidia"
    assert eff_cfg.model == "nvidia/nemotron-3-super-120b-a12b"
    assert eff_cfg.api_key == "nvapi-testkey-12345"

    # Spawning a subagent creates it with the parent's config
    with patch("cord.subagents.base_subagent.Subagent.run", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = SubagentResult(
            role="researcher",
            task="Find all auth handlers",
            success=True,
            summary="Found 2 handlers",
            tool_calls_count=1,
            model=eff_cfg.model,
            provider=eff_cfg.provider,
        )

        spawn_tool = SpawnSubagentTool(manager=manager)
        res = await spawn_tool.execute(role="researcher", task="Find all auth handlers")

        assert res.success is True
        assert "nvidia" in res.output
        assert "nvidia/nemotron-3-super-120b-a12b" in res.output


@pytest.mark.asyncio
async def test_subagent_dynamic_config_sync_on_parent_change(tmp_path):
    """Verifies that changing the parent agent config immediately syncs to subagents."""
    cfg = CordConfig(
        workspace_dir=str(tmp_path),
        provider="nvidia",
        model="nvidia/nemotron-3-super-120b-a12b",
    )
    guard = PermissionGuard(cfg)
    registry = ToolRegistry(guard)
    manager = SubagentManager(config=cfg, available_tools=registry.tools)
    agent = CordAgent(config=cfg, tool_registry=registry, subagent_manager=manager)

    # Now simulate switching provider/model in parent agent (e.g. /provider openrouter)
    new_cfg = CordConfig(
        workspace_dir=str(tmp_path),
        provider="openrouter",
        model="nousresearch/hermes-3-llama-3.1-405b",
        base_url="https://openrouter.ai/api/v1",
        api_key="sk-or-v1-testkey",
    )
    agent.config = new_cfg

    # Subagent manager must immediately reflect new config
    eff_cfg = manager.get_effective_config()
    assert eff_cfg.provider == "openrouter"
    assert eff_cfg.model == "nousresearch/hermes-3-llama-3.1-405b"
    assert eff_cfg.base_url == "https://openrouter.ai/api/v1"
    assert eff_cfg.api_key == "sk-or-v1-testkey"


@pytest.mark.asyncio
async def test_subagent_explicit_model_and_provider_override(tmp_path):
    """Verifies that explicit model/provider parameters override the inherited defaults."""
    cfg = CordConfig(
        workspace_dir=str(tmp_path),
        provider="nvidia",
        model="nvidia/nemotron-3-super-120b-a12b",
    )
    guard = PermissionGuard(cfg)
    registry = ToolRegistry(guard)
    manager = SubagentManager(config=cfg, available_tools=registry.tools)

    with patch("cord.subagents.base_subagent.Subagent.run", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = SubagentResult(
            role="coder",
            task="Write tests",
            success=True,
            summary="Tests written",
            tool_calls_count=1,
            model="anthropic/claude-3.7-sonnet",
            provider="openrouter",
        )

        spawn_tool = SpawnSubagentTool(manager=manager)
        res = await spawn_tool.execute(
            role="coder",
            task="Write tests",
            model="anthropic/claude-3.7-sonnet",
            provider="openrouter",
        )

        assert res.success is True
        assert "openrouter" in res.output
        assert "anthropic/claude-3.7-sonnet" in res.output


@pytest.mark.asyncio
async def test_subagent_tool_alias_resolution(tmp_path):
    """Verifies that requesting list_dir, grep_search, run_shell maps to real tools without errors."""
    cfg = CordConfig(workspace_dir=str(tmp_path))
    tools_dict = {
        "read_file": ReadFileTool(),
        "list_directory": ListDirectoryTool(),
        "search_files": SearchFilesTool(),
        "execute_command": ExecuteCommandTool(),
    }
    manager = SubagentManager(config=cfg, available_tools=tools_dict)

    # Resolve using aliases
    resolved = manager._resolve_tools(["list_dir", "grep_search", "run_shell", "read_file"])
    names = {t.name for t in resolved}
    assert "list_directory" in names
    assert "search_files" in names
    assert "execute_command" in names
    assert "read_file" in names


@pytest.mark.asyncio
async def test_tool_registry_alias_fallback(tmp_path):
    """Verifies that ToolRegistry.execute accepts aliases like list_dir and maps them."""
    cfg = CordConfig(workspace_dir=str(tmp_path))
    guard = PermissionGuard(cfg)
    registry = ToolRegistry(guard)
    registry.register(ListDirectoryTool())

    # list_directory is registered, but we call list_dir
    res = await registry.execute("list_dir", {"path": str(tmp_path)})
    assert res.success is True


@pytest.mark.asyncio
async def test_subagent_think_tool_interception(tmp_path):
    """Verifies that if a model emits a 'think' tool call, Subagent intercepts it safely."""
    cfg = CordConfig(workspace_dir=str(tmp_path))
    subagent = Subagent(
        name="test-subagent",
        role="coder",
        system_prompt="You are a coder.",
        config=cfg,
        tools=[ReadFileTool()],
    )

    # Simulate fake stream: turn 1 returns think tool call, turn 2 returns final answer
    from cord.core.llm import StreamChunk, ToolCallDelta

    turn = 0

    async def mock_stream_chat(*args, **kwargs):
        nonlocal turn
        turn += 1
        if turn == 1:
            yield StreamChunk(
                tool_call_delta=ToolCallDelta(
                    index=0,
                    id="call_think_0",
                    name="think",
                    arguments='{"thought": "We should read the main file first"}',
                )
            )
        else:
            yield StreamChunk(text="Finished planning.")

    subagent.llm.stream_chat = mock_stream_chat
    res = await subagent.run("Refactor database connection")

    assert res.success is True
    # The 'think' tool call was handled without crashing and turn 2 provided the final answer
    assert "Finished planning." in res.summary
