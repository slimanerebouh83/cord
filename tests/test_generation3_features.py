"""CORD Tests - Generation 3.0 Architecture Features
Verifies:
1. Session Isolation & Rich UI Events Persistence
2. Stealth Window Manager (Hide / Show Terminal)
3. Swarm Message Bus & Concurrency Pool (1000-Worker Architecture)
4. Native CORD MCP Server (JSON-RPC initialize, tools/list, tools/call)
5. DuckDuckGo Web Search Tool
6. Voice Engine (TTS cleaning/queueing, STT, Voice trigger parsing)
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

from cord.memory.sessions import SessionManager
from cord.utils.window_manager import WindowManager
from cord.subagents.message_bus import SwarmMessageBus
from cord.subagents.manager import SubagentManager
from cord.mcp.server import MCPServer
from cord.tools.network.duckduckgo_search import DuckDuckGoSearchTool
from cord.voice.tts import TextToSpeech
from cord.voice.live_mode import LiveVoiceSession
from cord.voice.audio_recorder import AudioRecorder
from cord.core.config import CordConfig


@pytest.fixture
def tmp_session_mgr(tmp_path):
    return SessionManager(sessions_dir=tmp_path / "sessions")


def test_session_isolation_and_ui_events(tmp_session_mgr):
    """Verifies that sessions are strictly isolated and rich ui_events persist correctly."""
    tmp_session_mgr.record_ui_event("user_query", text="Build a fast API")
    tmp_session_mgr.record_ui_event("thinking", text="Analyzing requirements...")
    tmp_session_mgr.record_ui_event("assistant_text", text="API built successfully.", model="claude-3-7-sonnet")
    tmp_session_mgr.record_ui_event("tool_call", name="read_file", args={"path": "app.py"}, output="code", success=True, elapsed=0.01)

    # Save session
    messages = [
        {"role": "user", "content": "Build a fast API"},
        {"role": "assistant", "content": "API built successfully."},
    ]
    path = tmp_session_mgr.save_session(
        messages=messages,
        model="claude-3-7-sonnet",
        mode="agent",
        target_file="app.py",
    )
    assert path.exists()

    # Clear current session (isolation test)
    tmp_session_mgr.clear_current_session()
    assert len(tmp_session_mgr.current_ui_events) == 0
    assert tmp_session_mgr.current_target_file is None

    # Load session back
    loaded = tmp_session_mgr.load_session(path.stem)
    assert loaded is not None
    assert loaded["session_id"] == path.stem
    assert loaded["target_file"] == "app.py"
    assert len(loaded["ui_events"]) == 4
    assert loaded["ui_events"][0]["type"] == "user_query"
    assert loaded["ui_events"][1]["type"] == "thinking"
    assert loaded["ui_events"][2]["type"] == "assistant_text"
    assert loaded["ui_events"][3]["type"] == "tool_call"


def test_window_manager_stealth():
    """Verifies WindowManager state toggling and safe fallback."""
    wm = WindowManager()
    with patch("ctypes.windll.user32.ShowWindow", return_value=1) as mock_show, \
         patch("ctypes.windll.user32.SetForegroundWindow", return_value=1), \
         patch.object(wm, "get_hwnd", return_value=12345):
        
        # Test hide
        res = wm.hide_terminal()
        assert res is True
        assert wm.is_hidden is True
        mock_show.assert_called_with(12345, 0)  # SW_HIDE = 0

        # Test show
        res = wm.show_terminal()
        assert res is True
        assert wm.is_hidden is False


def test_swarm_message_bus():
    """Verifies peer-to-peer message routing and broadcasts across subagents."""
    bus = SwarmMessageBus()
    bus.register_agent("worker_alpha")
    bus.register_agent("worker_beta")
    bus.register_agent("worker_gamma")

    # Direct message
    bus.send(sender_id="worker_alpha", recipient_id="worker_beta", content="Please inspect tests")
    
    # Check inboxes
    inbox_gamma = bus.get_inbox("worker_gamma")
    assert len(inbox_gamma) == 0

    inbox_beta = bus.get_inbox("worker_beta")
    assert len(inbox_beta) == 1
    assert inbox_beta[0]["from"] == "worker_alpha"
    assert inbox_beta[0]["content"] == "Please inspect tests"

    # Second read returns 0 because unread_only=True
    assert len(bus.get_inbox("worker_beta")) == 0

    # Broadcast
    bus.broadcast(sender_id="worker_alpha", content="Deploying swarm v2")
    inbox_beta_2 = bus.get_inbox("worker_beta")
    inbox_gamma_2 = bus.get_inbox("worker_gamma")
    assert len(inbox_beta_2) == 1
    assert len(inbox_gamma_2) == 1
    assert inbox_beta_2[0]["content"] == "Deploying swarm v2"
    assert inbox_gamma_2[0]["content"] == "Deploying swarm v2"


@pytest.mark.asyncio
async def test_swarm_concurrency_pool():
    """Verifies mass subagent concurrency pool executing tasks smoothly."""
    config = CordConfig()
    mgr = SubagentManager(config=config, available_tools={})

    # Mock Subagent.run to simulate fast completion
    with patch("cord.subagents.base_subagent.Subagent.run") as mock_run:
        from cord.subagents.base_subagent import SubagentResult
        mock_run.return_value = SubagentResult(
            role="coder",
            task="Optimize subtask",
            success=True,
            summary="Completed micro-task.",
            tool_calls_count=1,
        )

        tasks = [
            {"role": "coder", "prompt": f"Subtask #{i}"}
            for i in range(25)
        ]

        res = await mgr.run_swarm(
            goal="Refactor system components in parallel",
            tasks=tasks,
            max_concurrency=10,
        )

        assert res["total_tasks"] == 25
        assert res["completed"] == 25
        assert res["failed"] == 0
        assert len(res["results"]) == 25


@pytest.mark.asyncio
async def test_mcp_server_protocol():
    """Verifies CORD MCP Server JSON-RPC 2.0 handshake, tools listing, and execution."""
    server = MCPServer()

    # 1. initialize
    init_resp = await server.handle_request({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "clientInfo": {"name": "test-client", "version": "1.0"},
        },
    })
    assert init_resp["result"]["serverInfo"]["name"] == "cord-mcp-server"

    # 2. tools/list
    list_resp = await server.handle_request({
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {},
    })
    tools = list_resp["result"]["tools"]
    assert len(tools) > 30
    tool_names = [t["name"] for t in tools]
    assert "duckduckgo_search" in tool_names
    assert "swarm_dispatch" in tool_names

    # 3. tools/call
    with patch.object(server.tools, "execute") as mock_exec:
        from cord.tools.base import ToolResult
        mock_exec.return_value = ToolResult(output="System healthy", success=True)
        call_resp = await server.handle_request({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "get_system_info", "arguments": {}},
        })
        assert call_resp["result"]["isError"] is False
        assert call_resp["result"]["content"][0]["text"] == "System healthy"

    # 4. ping
    ping_resp = await server.handle_request({
        "jsonrpc": "2.0",
        "id": 4,
        "method": "ping",
        "params": {},
    })
    assert ping_resp["result"] == {}


@pytest.mark.asyncio
async def test_duckduckgo_search_tool():
    """Verifies DuckDuckGoSearchTool schema and parsing behavior."""
    tool = DuckDuckGoSearchTool()
    schema = tool.get_schema()
    assert schema["type"] == "object"
    assert "query" in schema["required"]

    # Mock HTTP response from DuckDuckGo
    sample_html = """
    <div class="result__body">
        <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fpython.org">Python Official</a>
        <a class="result__snippet">Python is a high-level programming language.</a>
    </div>
    """
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = sample_html
        mock_post.return_value = mock_resp

        res = await tool.execute(query="python")
        assert res.success is True
        assert "Python Official" in res.output
        assert "https://python.org" in res.output


def test_voice_tts_cleaning_and_triggers():
    """Verifies TTS text sanitation and LiveVoiceSession triggers."""
    tts_engine = TextToSpeech()
    raw_markdown = "Here is the code: ```python\ndef hello(): pass\n``` and check `variable_name` [Link](https://cord.ai)!"
    cleaned = tts_engine._clean_text_for_speech(raw_markdown)
    assert "```" not in cleaned
    assert "Code block executed" in cleaned
    assert "variable_name" in cleaned
    assert "https://cord.ai" not in cleaned

    # Live session trigger tests
    agent_mock = MagicMock()
    live = LiveVoiceSession(agent=agent_mock, config=CordConfig())
    
    # Hide triggers
    assert live.is_hide_command("please hide terminal now") is True
    assert live.is_hide_command("minimize terminal please") is True
    assert live.is_hide_command("hello world") is False

    # Show triggers
    assert live.is_show_command("show terminal") is True
    assert live.is_show_command("restore terminal") is True
    assert live.is_show_command("run code") is False

    # Exit triggers
    assert live.is_exit_command("stop") is True
    assert live.is_exit_command("exit") is True
    assert live.is_exit_command("continue") is False


@pytest.mark.asyncio
async def test_computer_act_and_mouse_scrolling():
    """Verifies that computer_act and computer_mouse can execute downward and upward scrolling."""
    from cord.tools.computer.computer_act import ComputerActTool
    from cord.tools.computer.computer_mouse import ComputerMouseTool

    act_tool = ComputerActTool()
    mouse_tool = ComputerMouseTool()

    with patch("cord.tools.computer.computer_act._send_mouse_event") as mock_act_send, \
         patch("cord.tools.computer.computer_act._activate_window_at"), \
         patch("cord.tools.computer.computer_act._glide_cursor_to"), \
         patch("cord.tools.computer.computer_mouse._send_mouse_event") as mock_mouse_send, \
         patch("cord.tools.computer.computer_mouse._activate_window_at"), \
         patch("cord.tools.computer.computer_mouse._glide_cursor_to"):

        # 1. Test computer_act scroll_down
        res_down = await act_tool.execute(action="scroll_down", x=500, y=500, scroll_amount=-600)
        assert res_down.success is True
        assert "Scrolled page down" in res_down.output
        assert mock_act_send.call_count >= 5

        # 2. Test computer_act page_down
        with patch.object(act_tool._kb, "execute", new_callable=AsyncMock) as mock_kb:
            mock_kb.return_value = MagicMock(success=True)
            res_pagedown = await act_tool.execute(action="page_down")
            assert res_pagedown.success is True
            assert "Pressed PageDown" in res_pagedown.output

        # 3. Test computer_mouse scroll
        res_mouse = await mouse_tool.execute(action="scroll", x=600, y=600, scroll_amount=-480)
        assert res_mouse.success is True
        assert "Scrolled mouse wheel" in res_mouse.output
        assert mock_mouse_send.call_count >= 4

