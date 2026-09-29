"""Tests for ModelRouter and Computer Use safety/validation"""
import pytest
from cord.models.model_router import ModelRouter, ModelRole
from cord.vision.safety import ComputerSafetyManager, ComputerSafetyLevel
from cord.tools.computer.computer_mouse import ComputerMouseTool
from cord.tools.computer.computer_keyboard import ComputerKeyboardTool
from cord.tools.computer.computer_window import ComputerWindowTool


def test_model_router_role_resolution():
    router = ModelRouter(default_model="custom/my-model")
    assert router.resolve_for_role(ModelRole.CODING) == "custom/my-model"

    # Explicit override per role
    router.set_role_model(ModelRole.FAST, "groq/llama-3.1-8b-instant")
    assert router.resolve_for_role(ModelRole.FAST) == "groq/llama-3.1-8b-instant"
    assert router.resolve_for_role(ModelRole.CODING) == "custom/my-model"

    # Direct preference override
    assert router.resolve_for_role(ModelRole.CODING, preferred_model="anthropic/claude-3.7-sonnet") == "anthropic/claude-3.7-sonnet"


def test_computer_safety_levels_and_kill_switch():
    safety = ComputerSafetyManager()
    safety.safety_level = ComputerSafetyLevel.INTERACTION
    safety.reset_emergency_stop()

    # Valid interaction action
    allowed, msg = safety.validate_action("click", x=100, y=100)
    assert allowed is True

    # Out of bounds coordinates
    w, h = safety.screen_size
    allowed, msg = safety.validate_action("move", x=w + 500, y=h + 500)
    assert allowed is False
    assert "out of screen bounds" in msg

    # Negative coordinates
    allowed, msg = safety.validate_action("move", x=-10, y=100)
    assert allowed is False

    # READ_ONLY level blocks mouse clicks
    safety.safety_level = ComputerSafetyLevel.READ_ONLY
    allowed, msg = safety.validate_action("click", x=100, y=100)
    assert allowed is False
    assert "Safety level is READ_ONLY" in msg

    # Screenshot is allowed in READ_ONLY
    allowed, msg = safety.validate_action("screenshot")
    assert allowed is True

    # Kill switch halts everything
    safety.trigger_emergency_stop("Test Stop")
    assert safety.is_stopped() is True
    allowed, msg = safety.validate_action("screenshot")
    assert allowed is False
    assert "Emergency kill switch is ACTIVE" in msg

    # Reset
    safety.reset_emergency_stop()
    assert safety.is_stopped() is False


def test_computer_tools_schemas():
    mouse = ComputerMouseTool()
    assert mouse.name == "computer_mouse"
    assert "click" in mouse.parameters["properties"]["action"]["enum"]

    kb = ComputerKeyboardTool()
    assert kb.name == "computer_keyboard"
    assert "hotkey" in kb.parameters["properties"]["action"]["enum"]

    win = ComputerWindowTool()
    assert win.name == "computer_window"
    assert "focus" in win.parameters["properties"]["action"]["enum"]


def test_computer_act_tool_schema_and_modes():
    from cord.tools.computer.computer_act import ComputerActTool
    from cord.tools import get_default_tools
    from cord.core.modes import MODE_PROFILES, OperationalMode

    act = ComputerActTool()
    assert act.name == "computer_act"
    actions = act.parameters["properties"]["action"]["enum"]
    assert "click_and_type" in actions
    assert "click_point" in actions
    assert "youtube_like" in actions
    assert "batch" in actions

    # Registered in default tools
    tools = get_default_tools()
    tool_names = {t.name for t in tools}
    assert "computer_act" in tool_names

    # Filtered in COMPUTER mode
    comp_profile = MODE_PROFILES[OperationalMode.COMPUTER]
    assert "computer_act" in comp_profile.tool_filter


def test_ai_cursor_hud():
    from cord.vision.ai_cursor import ai_cursor
    # Must not raise exceptions
    ai_cursor.show_pointer(250, 350)
    ai_cursor.show_click(250, 350, button="left")
    assert ai_cursor.current_x == 250
    assert ai_cursor.current_y == 350


@pytest.mark.asyncio
async def test_computer_act_execution(monkeypatch):
    from cord.tools.computer.computer_act import ComputerActTool
    from unittest.mock import MagicMock, AsyncMock

    act = ComputerActTool()

    # Mock internal mouse and keyboard primitives
    monkeypatch.setattr("cord.tools.computer.computer_act._activate_window_at", lambda x, y: None)
    monkeypatch.setattr("cord.tools.computer.computer_act._glide_cursor_to", lambda x, y: None)
    monkeypatch.setattr("cord.tools.computer.computer_act._send_mouse_event", lambda flags: None)
    monkeypatch.setattr(act._kb, "execute", AsyncMock(return_value=MagicMock(success=True, output="ok")))

    # 1. click_point
    res = await act.execute(action="click_point", x=400, y=500)
    assert res.success is True
    assert "Clicked point at (400, 500)" in res.output

    # 2. click_and_type
    res = await act.execute(action="click_and_type", x=400, y=500, text="hello cord", press_enter=True)
    assert res.success is True
    assert "typed 'hello cord' and pressed Enter." in res.output

    # 3. batch
    steps = [
        {"action": "click", "x": 100, "y": 100},
        {"action": "type", "text": "test"},
        {"action": "key", "key": "enter"},
    ]
    res = await act.execute(action="batch", steps=steps)
    assert res.success is True
    assert "3 actions executed" in res.output


@pytest.mark.asyncio
async def test_computer_keyboard_actions():
    from cord.tools.computer.computer_keyboard import ComputerKeyboardTool
    kb = ComputerKeyboardTool()

    # 1. Test type action
    res = await kb.execute(action="type", text="Hello CORD 2.0!")
    assert res.success is True
    assert "typed 15 characters" in res.output.lower()

    # 2. Test key action
    res_key = await kb.execute(action="key", key="enter")
    assert res_key.success is True
    assert "enter" in res_key.output

    # 3. Test hotkey action
    res_hotkey = await kb.execute(action="hotkey", hotkey="ctrl+c")
    assert res_hotkey.success is True
    assert "ctrl+c" in res_hotkey.output
