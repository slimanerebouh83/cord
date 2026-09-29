"""
Tests for browser_media tool, auto-failover, telemetry speedometer, and action menu.
"""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

from cord.tools.computer.browser_media import BrowserMediaTool
from cord.tools import get_default_tools
from cord.core.config import CordConfig
from cord.core.agent import CordAgent
from cord.core.llm import LLMError, StreamChunk
from cord.tools.registry import ToolRegistry
from cord.ui.renderer import ChatRenderer


@pytest.mark.asyncio
async def test_browser_media_search_youtube():
    tool = BrowserMediaTool()
    opened_urls = []
    tool._open_url_native = lambda url: opened_urls.append(url)

    res = await tool.execute(action="search_youtube", query="Sankara video")
    assert res.success is True
    assert len(opened_urls) == 1
    assert "youtube.com/results?search_query=Sankara+video" in opened_urls[0]
    assert "Sankara video" in res.output


@pytest.mark.asyncio
async def test_browser_media_web_search():
    tool = BrowserMediaTool()
    opened_urls = []
    tool._open_url_native = lambda url: opened_urls.append(url)

    res = await tool.execute(action="web_search", query="python 3.11 release notes", engine="google")
    assert res.success is True
    assert len(opened_urls) == 1
    assert "google.com/search?q=python+3.11+release+notes" in opened_urls[0]


@pytest.mark.asyncio
async def test_browser_media_keys():
    tool = BrowserMediaTool()
    with patch("ctypes.windll.user32.keybd_event") as mock_keybd:
        res = await tool.execute(action="media_key", key="play_pause")
        assert res.success is True
        assert "play_pause" in res.output
        assert mock_keybd.call_count >= 2


def test_tool_registry_has_browser_media():
    tools = get_default_tools()
    names = [t.name for t in tools]
    assert "browser_media" in names
    assert "windows_app" in names
    assert len(tools) >= 50


def test_auto_failover_disabled_by_default():
    cfg = CordConfig(
        base_url="https://integrate.api.nvidia.com/v1",
        model="deepseek-ai/deepseek-v4-flash-0731",
    )
    # Auto-failover must be disabled by default so the user's model is never overridden
    assert cfg.auto_failover is False
    fallback = cfg.get_fallback_candidate()
    assert fallback is None


from cord.core.permissions import PermissionGuard

@pytest.mark.asyncio
async def test_agent_preserves_model_on_error():
    cfg = CordConfig(
        base_url="https://integrate.api.nvidia.com/v1",
        model="deepseek-ai/deepseek-v4-flash-0731",
    )
    guard = PermissionGuard(cfg)
    registry = ToolRegistry(guard)
    agent = CordAgent(config=cfg, tool_registry=registry)

    async def mock_stream_chat(*args, **kwargs):
        raise LLMError("Nvidia NIM Server Congested: ReadTimeout")
        yield

    with patch.object(agent.llm, "stream_chat", side_effect=mock_stream_chat):
        response = await agent.step("Test resilience without auto-failover")
        assert "Error:" in response
        # Model must remain strictly intact
        assert agent.config.model == "deepseek-ai/deepseek-v4-flash-0731"
        assert agent.latest_telemetry.get("failed_over") is not True


def test_telemetry_speedometer_rendering():
    # Verify no exceptions raised during telemetry print
    ChatRenderer.render_turn_telemetry(
        tokens=240,
        tok_per_sec=52.4,
        ttft_sec=0.75,
        model_name="openai/gpt-oss-20b",
        failed_over=True,
    )
