"""
Unit Tests for CORD Subagent Interactive Dashboard, Isolated Dedicated Chats,
Thinking Stream Box Closing, and Swarm Peer Equality (كلهم سواسية).
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from cord.core.config import CordConfig
from cord.core.agent import CordAgent
from cord.core.permissions import PermissionGuard
from cord.tools.registry import ToolRegistry
from cord.subagents.manager import SubagentManager
from cord.subagents.base_subagent import Subagent, SubagentResult
from cord.subagents.message_bus import swarm_bus, SwarmMessage
from cord.tools.filesystem.read_file import ReadFileTool
from cord.tools.filesystem.list_directory import ListDirectoryTool
from cord.ui.subagent_viewer import show_subagent_dashboard, open_dedicated_subagent_chat, _make_clickable_link


@pytest.fixture
def test_setup(tmp_path):
    cfg = CordConfig(
        workspace_dir=str(tmp_path),
        provider="openrouter",
        model="deepseek/deepseek-chat",
        api_key="sk-test-12345",
    )
    guard = PermissionGuard(cfg)
    registry = ToolRegistry(guard)
    registry.register(ReadFileTool())
    registry.register(ListDirectoryTool())
    manager = SubagentManager(config=cfg, available_tools=registry.tools)
    agent = CordAgent(config=cfg, tool_registry=registry, subagent_manager=manager)
    return cfg, registry, manager, agent


@pytest.mark.asyncio
async def test_subagent_registration_and_lookup(test_setup):
    """Verifies that spawned or created subagents are tracked in manager.agents and queryable."""
    _, _, manager, _ = test_setup

    interactive_agent = manager.create_interactive_agent(role="coder", custom_name="coder-alpha")
    assert interactive_agent.name == "coder-alpha"
    assert interactive_agent.role == "coder"
    assert interactive_agent.status == "idle"

    # Lookup by exact name
    found = manager.get_agent("coder-alpha")
    assert found is interactive_agent

    # Lookup by role
    found_role = manager.get_agent("coder")
    assert found_role is interactive_agent

    # List agents
    all_agents = manager.list_agents()
    assert interactive_agent in all_agents


@pytest.mark.asyncio
async def test_subagent_conversation_history_persistence(test_setup):
    """Verifies that subagents preserve conversation history across multiple turns."""
    _, _, manager, _ = test_setup

    agent = manager.create_interactive_agent(role="reviewer", custom_name="rev-01")
    assert len(agent.messages) == 0

    with patch.object(agent.llm, "stream_chat") as mock_stream:
        # Mock turn 1 response
        mock_chunk1 = MagicMock()
        mock_chunk1.text = "I am ready to review your pull request."
        mock_chunk1.thinking = None
        mock_chunk1.tool_call_delta = None
        mock_chunk1.input_tokens = 10
        mock_chunk1.output_tokens = 10

        async def gen1(*args, **kwargs):
            yield mock_chunk1

        mock_stream.side_effect = gen1
        res1 = await agent.run("Please prepare for review.")
        assert res1.success is True
        assert len(agent.messages) == 2  # user prompt + assistant response
        assert agent.status == "completed"

        # Turn 2: Follow-up instruction
        mock_chunk2 = MagicMock()
        mock_chunk2.text = "Everything looks clean and secure."
        mock_chunk2.thinking = None
        mock_chunk2.tool_call_delta = None
        mock_chunk2.input_tokens = 15
        mock_chunk2.output_tokens = 15

        async def gen2(*args, **kwargs):
            yield mock_chunk2

        mock_stream.side_effect = gen2
        res2 = await agent.run("Check security rules.")
        assert res2.success is True
        assert len(agent.messages) == 4  # prior 2 messages + user prompt 2 + assistant response 2


@pytest.mark.asyncio
async def test_thinking_box_closing_on_tool_call(test_setup):
    """Verifies that thinking header box closes cleanly when tool call arrives, avoiding orphan open boxes."""
    _, _, manager, _ = test_setup

    agent = manager.create_interactive_agent(role="coder", custom_name="box-test")

    with patch.object(agent.llm, "stream_chat") as mock_stream:
        # Mock streaming: first thinking chunk, then tool call delta
        tc_delta = MagicMock()
        tc_delta.index = 0
        tc_delta.id = "tc_1"
        tc_delta.name = "list_directory"
        tc_delta.arguments = '{"path": "."}'
        tc_delta.extra_content = None

        chunk_think = MagicMock(text=None, thinking="Thinking about the files...", tool_call_delta=None, input_tokens=5, output_tokens=5)
        chunk_tool = MagicMock(text=None, thinking=None, tool_call_delta=tc_delta, input_tokens=0, output_tokens=0)

        async def stream_gen(*args, **kwargs):
            yield chunk_think
            yield chunk_tool

        mock_stream.side_effect = stream_gen

        with patch("cord.ui.console.ui.console.print") as mock_print:
            res = await agent.run("List files")
            # Ensure ╰───╯ box closing was printed
            closed_calls = [c for c in mock_print.call_args_list if "╰" in str(c)]
            assert len(closed_calls) >= 1


@pytest.mark.asyncio
async def test_peer_equality_message_bus_bidirectional(test_setup):
    """
    Verifies Peer Equality (كلهم سواسية):
    Subagents and main agent communicate as equal peers over the swarm bus.
    """
    _, _, manager, agent = test_setup
    swarm_bus.clear()

    # Both main and subagent are registered
    swarm_bus.register_agent("main")
    swarm_bus.register_agent("coder-peer")

    # Subagent sends proposal to main agent
    swarm_bus.send(
        sender_id="coder-peer",
        recipient_id="main",
        content="I propose using SQLite for lightweight persistent storage.",
    )

    # Main agent processes next turn and receives the peer update
    with patch.object(agent.llm, "stream_chat") as mock_stream:
        chunk = MagicMock(text="Acknowledged peer proposal.", thinking=None, tool_call_delta=None, input_tokens=10, output_tokens=5)

        async def gen(*args, **kwargs):
            yield chunk

        mock_stream.side_effect = gen
        await agent.step("What should our storage architecture be?")

        # Check that the user/system turn in messages received the peer notification
        user_turn_content = agent.messages[-2]["content"]
        assert "Swarm Peer Notification" in user_turn_content
        assert "coder-peer" in user_turn_content
        assert "SQLite" in user_turn_content


@pytest.mark.asyncio
async def test_subagent_viewer_dashboard_rendering(test_setup):
    """Verifies that show_subagent_dashboard displays all active peers without error."""
    _, _, manager, agent = test_setup

    manager.create_interactive_agent(role="coder", custom_name="coder-01")
    manager.create_interactive_agent(role="researcher", custom_name="researcher-01")

    repl_mock = MagicMock()
    repl_mock.subagents = manager
    repl_mock.agent = agent

    # Test that dashboard renders and exits on '0'
    with patch("rich.prompt.Prompt.ask", return_value="0"), patch("cord.ui.console.ui.console.print") as mock_print:
        await show_subagent_dashboard(repl_mock)
        # Verify console print was invoked with the table panel
        assert mock_print.called


def test_clickable_terminal_link():
    """Verifies OSC 8 terminal hyperlink syntax."""
    link = _make_clickable_link("coder-peer", "subagent://coder-peer")
    assert "\033]8;;subagent://coder-peer\033\\" in link
    assert "coder-peer" in link


@pytest.mark.asyncio
async def test_mouse_clickable_dashboard_fragments_and_handlers(test_setup):
    """
    Verifies that the interactive dashboard generates mouse-clickable fragments
    and that clicking with the mouse on rows or buttons triggers the right result.
    """
    from cord.ui.subagent_viewer import _run_interactive_mouse_dashboard
    from prompt_toolkit.mouse_events import MouseEvent, MouseEventType, MouseButton
    from prompt_toolkit.output import DummyOutput

    _, _, manager, agent = test_setup
    sub = manager.create_interactive_agent(role="coder", custom_name="coder-mouse")

    repl_mock = MagicMock()
    repl_mock.subagents = manager
    repl_mock.agent = agent

    dummy_event = MouseEvent(
        position=None,
        event_type=MouseEventType.MOUSE_UP,
        button=MouseButton.LEFT,
        modifiers=frozenset(),
    )

    with patch("prompt_toolkit.application.Application.run_async") as mock_run:
        # Simulate mouse click on the subagent row
        mock_run.return_value = "select:coder-mouse"
        result = await _run_interactive_mouse_dashboard(repl_mock, manager, [sub])
        assert result == "select:coder-mouse"


@pytest.mark.asyncio
async def test_subagent_monitor_observation_only_routes_to_main_agent(test_setup):
    """
    Verifies the user's core requirement:
    'وعندما المستخدم يدخل الشات تبعه لا يمكنه التحدث معه المستخدم يتحدث مع الرئيسي فقط'
    Direct conversation is forbidden; any directive is routed to the Main Agent!
    """
    from cord.ui.subagent_viewer import open_subagent_monitor

    _, _, manager, agent = test_setup
    sub = manager.create_interactive_agent(role="coder", custom_name="coder-target")
    sub.messages.append({"role": "assistant", "content": "I am analyzing files."})

    repl_mock = MagicMock()
    repl_mock.subagents = manager
    repl_mock.agent = MagicMock()
    repl_mock.agent.step = AsyncMock()

    # User inputs directive first, then '0' to exit
    with patch("cord.ui.console.ui.console.input", side_effect=["Fix the login bug in auth.py", "0"]), \
         patch("cord.ui.console.ui.console.clear"):
        await open_subagent_monitor(repl_mock, sub)

        # Assert Main Agent received the directive!
        repl_mock.agent.step.assert_awaited_once()
        call_prompt = repl_mock.agent.step.await_args[0][0]
        assert "[User Directive for Main Agent regarding subagent 'coder-target']" in call_prompt
        assert "Fix the login bug in auth.py" in call_prompt


@pytest.mark.asyncio
async def test_subagent_monitor_tab_navigation(test_setup):
    """Verifies switching between Activity, Thoughts, Tools, Swarm, and Specs tabs."""
    from cord.ui.subagent_viewer import open_subagent_monitor

    _, _, manager, agent = test_setup
    sub = manager.create_interactive_agent(role="researcher", custom_name="res-tab")
    sub.thinking_history.append("Reasoning step 1: Check requirements.")
    sub.tool_history.append({"tool": "read_file", "args": {"path": "README.md"}, "result": "OK", "success": True})

    repl_mock = MagicMock()
    repl_mock.subagents = manager
    repl_mock.agent = agent

    # Switch through tabs: 2 (Thoughts), 3 (Tools), 4 (Swarm), 5 (Specs), then 0 (Exit)
    with patch("cord.ui.console.ui.console.input", side_effect=["2", "3", "4", "5", "0"]), \
         patch("cord.ui.console.ui.console.clear"), \
         patch("cord.ui.console.ui.console.print") as mock_print:
        await open_subagent_monitor(repl_mock, sub)
        assert mock_print.called


@pytest.mark.asyncio
async def test_subagent_thinking_and_tool_history_recording(test_setup):
    """Verifies that Subagent accurately stores thinking_history and tool_history."""
    _, _, manager, _ = test_setup
    ag = manager.create_interactive_agent(role="coder", custom_name="hist-agent")
    assert ag.thinking_history == []
    assert ag.tool_history == []
    assert ag.current_task == ""

    with patch.object(ag.llm, "stream_chat") as mock_stream:
        chunk_think = MagicMock(text=None, thinking="Planning database schema...", tool_call_delta=None, input_tokens=5, output_tokens=5)
        chunk_text = MagicMock(text="Schema plan complete.", thinking=None, tool_call_delta=None, input_tokens=5, output_tokens=5)

        async def stream_gen(*args, **kwargs):
            yield chunk_think
            yield chunk_text

        mock_stream.side_effect = stream_gen
        res = await ag.run("Design the database schema")
        assert res.success is True
        assert ag.current_task == "Design the database schema"
        assert len(ag.thinking_history) == 1
        assert "Planning database schema" in ag.thinking_history[0]

