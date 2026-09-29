"""
Unit Tests for CORD UI Modernization, Electric Blue Theme, Split-Screen Sidebar,
Minimalist Tool Badges, and Massive 10,000+ Agent Swarm Mesh.
"""

import pytest
from unittest.mock import MagicMock, patch

from cord.ui.console import THEMES, CordConsole
from cord.ui.renderer import ChatRenderer
from cord.ui.split_view import sidebar_state, render_sidebar_panel
from cord.subagents.message_bus import SwarmMessageBus, SwarmMessage
from cord.tools.base import ToolResult


# ─────────────────────────────────────────────────────────────
# 1. Electric Blue Theme Tests
# ─────────────────────────────────────────────────────────────

def test_cord_blue_theme_configured():
    assert "cord_blue" in THEMES
    theme = THEMES["cord_blue"]
    assert theme.styles["info"].color.name == "#3b82f6"
    assert theme.styles["accent"].color.name == "#2563eb"

    # Verify default console theme is cord_blue
    c = CordConsole(theme_name="cord_blue")
    assert c.theme_name == "cord_blue"


# ─────────────────────────────────────────────────────────────
# 2. Minimalist Compact Tool Rendering Tests (Matching Image 1)
# ─────────────────────────────────────────────────────────────

def test_render_tool_execution_grep():
    renderer = ChatRenderer()
    res = ToolResult(success=True, output="line1\nline2\nline3\n", metadata={"matches": [1, 2, 3]})
    with patch("cord.ui.console.ui.console.print") as mock_print:
        renderer.render_tool_execution("search_files", {"query": "homepage|home.*button"}, res, 0.045)
        mock_print.assert_called_once()
        out_str = mock_print.call_args[0][0]
        assert "Grep" in out_str
        assert "homepage|home.*button" in out_str
        assert "3 matches" in out_str


def test_render_tool_execution_glob():
    renderer = ChatRenderer()
    res = ToolResult(success=True, output="f1.tsx\nf2.tsx\n", metadata={"count": 100})
    with patch("cord.ui.console.ui.console.print") as mock_print:
        renderer.render_tool_execution("find_files", {"pattern": "**/*.tsx"}, res, 0.080)
        mock_print.assert_called_once()
        out_str = mock_print.call_args[0][0]
        assert "Glob" in out_str
        assert "**/*.tsx" in out_str
        assert "100 matches" in out_str


def test_render_tool_execution_read():
    renderer = ChatRenderer()
    res = ToolResult(success=True, output="export const Button = () => ...")
    with patch("cord.ui.console.ui.console.print") as mock_print:
        renderer.render_tool_execution("read_file", {"path": "packages/console/app/src/component/header.tsx"}, res, 0.012)
        mock_print.assert_called_once()
        out_str = mock_print.call_args[0][0]
        assert "Read" in out_str
        assert "header.tsx" in out_str


def test_render_tool_execution_edit():
    renderer = ChatRenderer()
    res = ToolResult(success=True, output="File edited", metadata={"lines_added": 12, "lines_removed": 3})
    with patch("cord.ui.console.ui.console.print") as mock_print:
        renderer.render_tool_execution("edit_file", {"path": "packages/console/app/src/component/header.tsx"}, res, 0.025)
        mock_print.assert_called_once()
        out_str = mock_print.call_args[0][0]
        assert "Edit" in out_str
        assert "+12" in out_str
        assert "-3" in out_str


def test_render_tool_execution_command():
    renderer = ChatRenderer()
    res = ToolResult(success=True, output="test passed")
    with patch("cord.ui.console.ui.console.print") as mock_print:
        renderer.render_tool_execution("execute_command", {"command": "npm test"}, res, 1.25)
        mock_print.assert_called_once()
        out_str = mock_print.call_args[0][0]
        assert "Command" in out_str
        assert "npm test" in out_str


# ─────────────────────────────────────────────────────────────
# 3. Split-Screen Sidebar Tests (Matching Image 3)
# ─────────────────────────────────────────────────────────────

def test_split_sidebar_panel():
    sidebar_state.is_open = False
    assert sidebar_state.toggle() is True
    assert sidebar_state.is_open is True

    panel = render_sidebar_panel(tokens=66326, max_tokens=128000, cost_usd=0.46)
    assert panel is not None
    rendered_text = panel.renderable.plain
    assert "Leveraging agents for tasks" in rendered_text
    assert "66,326 tokens" in rendered_text
    assert "$0.46 spend" in rendered_text
    assert "MCP" in rendered_text
    assert "LSP" in rendered_text
    assert "Todo" in rendered_text
    assert "Swarm Mesh" in rendered_text


# ─────────────────────────────────────────────────────────────
# 4. Massive 10,000+ Agent Swarm Mesh Tests
# ─────────────────────────────────────────────────────────────

def test_swarm_bus_scales_to_10000_agents():
    bus = SwarmMessageBus(max_inbox_size=50)
    bus.provision_virtual_swarm(10000)
    assert bus.agent_count >= 10000

    # Register squads
    bus.register_agent("worker_001", squads=["squad:explorers"])
    bus.register_agent("worker_002", squads=["squad:explorers", "squad:coders"])
    bus.register_agent("worker_003", squads=["squad:coders"])

    # Multicast channel message
    bus.send("supervisor", "squad:explorers", "Search repository for type safety bugs")

    inbox1 = bus.get_inbox("worker_001")
    inbox2 = bus.get_inbox("worker_002")
    inbox3 = bus.get_inbox("worker_003")

    assert len(inbox1) == 1
    assert inbox1[0]["content"] == "Search repository for type safety bugs"
    assert len(inbox2) == 1
    assert len(inbox3) == 0  # Not in squad:explorers

    # High-speed batch dispatch of 500 messages
    batch = [
        SwarmMessage(sender_id="coord", recipient_id=f"agent_{i%100}", content=f"Task #{i}")
        for i in range(500)
    ]
    dispatched = bus.send_batch(batch)
    assert dispatched == 500
    assert bus.total_messages >= 501
