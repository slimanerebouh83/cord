"""Tests for Windows Computer-Use Automation Resilience and Normalization"""
import pytest
import sys
from unittest.mock import patch, MagicMock

from cord.vision.safety import computer_safety, ComputerSafetyManager, ComputerSafetyLevel
from cord.vision.vision_pipeline import vision_pipeline, resolve_screen_coordinates
from cord.tools.computer.computer_mouse import ComputerMouseTool
from cord.tools.computer.computer_keyboard import ComputerKeyboardTool
from cord.tools.computer.windows_apps import WindowsAppTool, WINDOWS_APP_SHORTCUTS
from cord.tools.computer.computer_act import ComputerActTool


def test_coordinate_normalization():
    sw, sh = computer_safety.screen_size
    assert sw > 0 and sh > 0

    # Normalized float coordinates [0.0, 1.0] -> physical pixels
    x, y = resolve_screen_coordinates(0.5, 0.5)
    assert x == sw // 2
    assert y == sh // 2

    # Corner normalized coordinates
    x_zero, y_zero = resolve_screen_coordinates(0.0, 0.0)
    assert x_zero == 0
    assert y_zero == 0

    x_full, y_full = resolve_screen_coordinates(1.0, 1.0)
    assert x_full == sw
    assert y_full == sh

    # Physical coordinates preserved
    x_phys, y_phys = resolve_screen_coordinates(250, 450)
    assert x_phys == 250
    assert y_phys == 450

    # Reference resolution scaling (e.g. vision model received 1280x720)
    x_scaled, y_scaled = resolve_screen_coordinates(640, 360, reference_width=1280, reference_height=720)
    assert x_scaled == sw // 2
    assert y_scaled == sh // 2


def test_safety_manager_normalized_coordinates():
    safety = ComputerSafetyManager.get_instance()
    # Normalized floats 0.0 to 1.0 must be accepted
    allowed, msg = safety.validate_action("click", x=0.25, y=0.75)
    assert allowed is True

    # Physical within bounds
    w, h = safety.screen_size
    allowed, msg = safety.validate_action("move", x=w // 2, y=h // 2)
    assert allowed is True

    # Coordinates out of bounds
    allowed, msg = safety.validate_action("move", x=w + 1000, y=h + 1000)
    assert allowed is False
    assert "out of screen bounds" in msg


def test_windows_app_shortcuts_coverage():
    assert "chrome" in WINDOWS_APP_SHORTCUTS
    assert "edge" in WINDOWS_APP_SHORTCUTS
    assert "calc" in WINDOWS_APP_SHORTCUTS
    assert "notepad" in WINDOWS_APP_SHORTCUTS
    assert "browser" in WINDOWS_APP_SHORTCUTS


@pytest.mark.asyncio
async def test_computer_mouse_normalized_coordinates_and_timings():
    mouse = ComputerMouseTool()
    sw, sh = computer_safety.screen_size

    with patch("cord.tools.computer.computer_mouse._glide_cursor_to") as mock_glide:
        res = await mouse.execute(action="move", x=0.5, y=0.5)
        assert res.success is True
        mock_glide.assert_called_once_with(sw // 2, sh // 2)

    with patch("cord.tools.computer.computer_mouse._glide_cursor_to"), \
         patch("cord.tools.computer.computer_mouse._activate_window_at"), \
         patch("cord.tools.computer.computer_mouse._send_mouse_event") as mock_event, \
         patch("time.sleep") as mock_sleep:
        res = await mouse.execute(action="click", x=0.5, y=0.5)
        assert res.success is True
        assert mock_event.call_count >= 2
        # Verify 40ms human hold time was called
        sleep_calls = [c.args[0] for c in mock_sleep.call_args_list]
        assert any(abs(s - 0.04) < 0.005 for s in sleep_calls)


@pytest.mark.asyncio
async def test_computer_keyboard_keys_list_support():
    kb = ComputerKeyboardTool()

    with patch("cord.tools.computer.computer_keyboard.press_virtual_key") as mock_down, \
         patch("cord.tools.computer.computer_keyboard.release_virtual_key") as mock_up:
        # Test keys as list
        res = await kb.execute(action="hotkey", keys=["ctrl", "enter"])
        assert res.success is True
        assert "ctrl+enter" in res.output
        assert mock_down.call_count == 2
        assert mock_up.call_count == 2


@pytest.mark.asyncio
async def test_computer_act_hotkey_call():
    act = ComputerActTool()

    with patch("cord.tools.computer.computer_act._activate_window_at"), \
         patch("cord.tools.computer.computer_act._glide_cursor_to"), \
         patch("cord.tools.computer.computer_act._send_mouse_event"), \
         patch.object(act._kb, "execute", return_value=MagicMock(success=True, output="ok")) as mock_kb:
        res = await act.execute(action="youtube_comment", text="Great video!", x=500, y=800)
        assert res.success is True
        # Check hotkey was called
        hotkey_calls = [c for c in mock_kb.call_args_list if c.kwargs.get("action") == "hotkey"]
        assert len(hotkey_calls) == 1
        assert hotkey_calls[0].kwargs.get("hotkey") == "ctrl+enter"


def test_vision_pipeline_capture():
    res = vision_pipeline.capture_screenshot(save_to_disk=False)
    assert res is not None
    assert res["width"] > 0
    assert res["height"] > 0
    assert len(res["base64"]) > 0
    assert res["data_uri"].startswith("data:image/jpeg;base64,")


@pytest.mark.asyncio
async def test_computer_act_compound_sequence():
    act = ComputerActTool()

    with patch("cord.tools.computer.computer_act._activate_window_at"), \
         patch("cord.tools.computer.computer_act._glide_cursor_to"), \
         patch("cord.tools.computer.computer_act._send_mouse_event"), \
         patch("cord.tools.computer.computer_act.ai_cursor.show_click"), \
         patch.object(act._kb, "execute", return_value=MagicMock(success=True, output="ok")):

        steps = [
            {"action": "scroll_down", "amount": -800},
            {"action": "click", "x": 500, "y": 300},
            {"action": "scroll_down", "amount": -600},
            {"action": "chord", "keys": ["ctrl", "c"]},
        ]

        res = await act.execute(action="sequence", steps=steps)
        assert res.success is True
        assert "4/4 actions in" in res.output
        assert "Scrolled down 800px" in res.output
        assert "Left-clicked at (500, 300)" in res.output
        assert "Scrolled down 600px" in res.output
        assert "Simultaneous chord [ctrl+c]" in res.output


@pytest.mark.asyncio
async def test_computer_act_freedom_of_execution_alias():
    act = ComputerActTool()

    with patch.object(act._kb, "execute", return_value=MagicMock(success=True, output="ok")):
        # Auto-routing: passing sequence parameter directly without action="sequence"
        seq = [
            {"action": "wait", "delay_ms": 10},
            {"action": "key", "key": "enter"},
        ]
        res = await act.execute(action="", sequence=seq)
        assert res.success is True
        assert "2/2 actions in" in res.output
        assert "Waited 10ms" in res.output
        assert "Pressed key 'enter'" in res.output


@pytest.mark.asyncio
async def test_computer_keyboard_simultaneous_chord():
    kb = ComputerKeyboardTool()

    with patch("cord.tools.computer.computer_keyboard.press_keys_simultaneously") as mock_press, \
         patch("cord.tools.computer.computer_keyboard.release_keys_simultaneously") as mock_rel:

        res = await kb.execute(action="chord", keys=["ctrl", "shift", "esc"], hold_duration_ms=20)
        assert res.success is True
        assert "simultaneous multi-key chord [ctrl+shift+esc]" in res.output
        mock_press.assert_called_once()
        mock_rel.assert_called_once()
        # Verify 3 virtual keys were sent
        assert len(mock_press.call_args[0][0]) == 3


@pytest.mark.asyncio
async def test_computer_keyboard_key_down_up_release_all():
    kb = ComputerKeyboardTool()

    with patch("cord.tools.computer.computer_keyboard.press_keys_simultaneously") as mock_press, \
         patch("cord.tools.computer.computer_keyboard.release_keys_simultaneously") as mock_rel:

        res_down = await kb.execute(action="key_down", keys=["shift"])
        assert res_down.success is True
        assert "Holding down key(s): shift" in res_down.output

        res_up = await kb.execute(action="key_up", keys=["shift"])
        assert res_up.success is True
        assert "Released key(s): shift" in res_up.output

        res_rel = await kb.execute(action="release_all")
        assert res_rel.success is True
        assert "Released all modifier keys" in res_rel.output

