"""
Unit Tests for CORD UI Customizer Tool, Immutable Name Security Guard,
Animated About Screen, and Ultra-Compact Micro Tool Cards.
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock

from cord.tools.ui_customizer_tool import CustomizeUITool, PROTECTED_APP_NAME
from cord.ui.about import show_about_screen, RELEASE_VERSION, GITHUB_REPO_URL
from cord.ui.renderer import ChatRenderer
from cord.tools.base import ToolResult
from cord.core.config import CordConfig


@pytest.mark.asyncio
async def test_ui_customizer_set_theme():
    tool = CustomizeUITool()
    res = await tool.execute(action="set_theme", theme="cord_blue")
    assert res.success is True
    assert res.metadata["theme"] == "cord_blue"

    res_invalid = await tool.execute(action="set_theme", theme="non_existent_theme")
    assert res_invalid.success is False
    assert "Unknown theme" in res_invalid.error


@pytest.mark.asyncio
async def test_ui_customizer_immutable_app_name_security_guard():
    """Security Guard Test: Any attempt to rename or disguise CORD must be strictly rejected."""
    tool = CustomizeUITool()
    res = await tool.execute(action="set_theme", theme="cyberpunk", app_name="DifferentApp")
    assert res.success is False
    assert res.metadata.get("security_violation") is True
    assert f"'{PROTECTED_APP_NAME}'" in res.error
    assert "strictly prohibited" in res.error

    res2 = await tool.execute(action="get_ui_state", new_name="HackedAgent")
    assert res2.success is False
    assert res2.metadata.get("security_violation") is True


@pytest.mark.asyncio
async def test_ui_customizer_language_and_compact_mode():
    tool = CustomizeUITool()
    # Test setting language to Arabic
    res_lang = await tool.execute(action="set_language", language="ar")
    assert res_lang.success is True
    assert res_lang.metadata["language"] == "ar"

    # Test toggling compact mode
    res_compact = await tool.execute(action="toggle_compact_mode", compact_mode=True)
    assert res_compact.success is True
    assert res_compact.metadata["compact_mode"] is True

    # Test get_ui_state
    res_state = await tool.execute(action="get_ui_state")
    assert res_state.success is True
    assert res_state.metadata["app_name"] == "CORD"


@pytest.mark.asyncio
async def test_show_about_screen_telemetry():
    cfg = CordConfig(model="claude-3.7-sonnet", provider="openrouter", permission_mode="yolo")
    with patch("cord.ui.console.ui.console.print") as mock_print, \
         patch("cord.ui.console.ui.console.clear"):
        await show_about_screen(config=cfg, animated=False)
        assert mock_print.call_count >= 3
        found_repo = any(GITHUB_REPO_URL in str(call[0][0]) for call in mock_print.call_args_list if call[0])
        assert found_repo is True


def test_compact_micro_card_tool_rendering():
    renderer = ChatRenderer()
    
    # 1. Read File Compact Card
    res_read = ToolResult(success=True, output="contents of file")
    with patch("cord.ui.console.ui.console.print") as mock_print:
        renderer.render_tool_execution("read_file", {"path": "cord/main.py", "start_line": 10, "end_line": 40}, res_read, elapsed=0.015)
        mock_print.assert_called_once()
        card_str = mock_print.call_args[0][0]
        assert "FILE SYSTEM" in card_str
        assert "Read" in card_str
        assert "main.py" in card_str
        assert "15ms" in card_str

    # 2. Edit File Compact Card with diff count
    res_edit = ToolResult(success=True, output="patched", metadata={"lines_added": 8, "lines_removed": 2})
    with patch("cord.ui.console.ui.console.print") as mock_print:
        renderer.render_tool_execution("edit_file", {"path": "cord/core/agent.py"}, res_edit, elapsed=0.025)
        mock_print.assert_called_once()
        card_str = mock_print.call_args[0][0]
        assert "SURGICAL WRITE" in card_str
        assert "Edit" in card_str
        assert "+8" in card_str
        assert "-2" in card_str
