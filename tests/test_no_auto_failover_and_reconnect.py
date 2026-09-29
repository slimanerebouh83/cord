"""
Tests verifying that Auto-Failover/Model Switching is completely removed,
and that CORD and Subagents reconnect with the EXACT SAME MODEL upon errors (HTTP 429, timeouts).
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from cord.core.config import CordConfig
from cord.core.agent import CordAgent
from cord.core.llm import LLMError, LLMClient, StreamChunk
from cord.core.permissions import PermissionGuard
from cord.tools.registry import ToolRegistry
from cord.subagents.manager import SubagentManager
from cord.subagents.base_subagent import Subagent


@pytest.fixture
def agent_and_subagent(tmp_path):
    target_model = "qwen/qwen3.8-27b:free"
    cfg = CordConfig(
        workspace_dir=str(tmp_path),
        provider="openrouter",
        model=target_model,
        base_url="https://openrouter.ai/api/v1",
        api_key="sk-or-v1-test",
        auto_failover=False,
    )
    guard = PermissionGuard(cfg)
    registry = ToolRegistry(guard)
    manager = SubagentManager(config=cfg, available_tools=registry.tools)
    agent = CordAgent(config=cfg, tool_registry=registry, subagent_manager=manager)
    return cfg, manager, agent, target_model


@pytest.mark.asyncio
async def test_subagent_reconnects_with_same_model_on_429(agent_and_subagent):
    """
    Verifies that when an HTTP 429 rate limit error occurs, the subagent
    reconnects and retries with the EXACT SAME MODEL without switching to any fallback.
    """
    cfg, manager, _, target_model = agent_and_subagent
    subagent = manager.create_interactive_agent(role="coder", custom_name="sub-coder")
    assert subagent.config.model == target_model

    attempt = 0

    async def mock_stream_with_transient_429(*args, **kwargs):
        nonlocal attempt
        attempt += 1
        if attempt == 1:
            raise LLMError("API Rate Limit or Quota Exceeded (HTTP 429): Provider returned error")
        else:
            yield StreamChunk(text="Finished coding after reconnection.")

    with patch.object(subagent.llm, "stream_chat", side_effect=mock_stream_with_transient_429), \
         patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:

        res = await subagent.run("Implement task")

        assert res.success is True
        assert "Finished coding after reconnection." in res.summary
        # Model must remain strictly intact
        assert subagent.config.model == target_model
        assert res.model == target_model
        assert attempt == 2
        mock_sleep.assert_called()


@pytest.mark.asyncio
async def test_subagent_never_switches_model_on_exhausted_error(agent_and_subagent):
    """
    Verifies that even if rate limit errors persist, the subagent NEVER switches models
    behind the user's back and preserves the original model in the result.
    """
    cfg, manager, _, target_model = agent_and_subagent
    subagent = manager.create_interactive_agent(role="reviewer", custom_name="sub-rev")

    async def mock_permanent_429(*args, **kwargs):
        raise LLMError("API Rate Limit or Quota Exceeded (HTTP 429)")
        yield

    with patch.object(subagent.llm, "stream_chat", side_effect=mock_permanent_429), \
         patch("asyncio.sleep", new_callable=AsyncMock):

        res = await subagent.run("Review PR")

        assert res.success is False
        assert "Failed with LLM error" in res.summary
        # Crucial: Model must remain unchanged!
        assert subagent.config.model == target_model
        assert res.model == target_model
        assert "nemotron" not in subagent.config.model.lower()


@pytest.mark.asyncio
async def test_main_agent_reconnects_with_same_model_on_rate_limit(agent_and_subagent):
    """
    Verifies that the main agent also reconnects on transient 429/connection issues
    and strictly retains the user's selected model.
    """
    _, _, agent, target_model = agent_and_subagent

    attempt = 0

    async def mock_stream_transient(*args, **kwargs):
        nonlocal attempt
        attempt += 1
        if attempt == 1:
            raise LLMError("API Rate Limit or Quota Exceeded (HTTP 429)")
        else:
            yield StreamChunk(text="Here is your solution.")

    with patch.object(agent.llm, "stream_chat", side_effect=mock_stream_transient), \
         patch("asyncio.sleep", new_callable=AsyncMock):

        res = await agent.step("Solve problem")

        assert "Here is your solution." in res
        assert agent.config.model == target_model
        assert attempt == 2


def test_config_candidate_always_none(agent_and_subagent):
    """Verifies get_fallback_candidate always returns None to forbid automatic model changes."""
    cfg, _, _, _ = agent_and_subagent
    assert cfg.get_fallback_candidate() is None
    cfg.auto_failover = True
    cfg.fallback_model = "nvidia-nemotron"
    assert cfg.get_fallback_candidate() is None
