"""
Tests for KINETIC-CORE Architecture & Self-Evolution Engine.
Verifies micro-packet streaming, minimum-jerk trajectory math, self-evolution adaptation,
reflex macro synthesis, and KineticActTool / ComputerActTool integration.
"""

import sys
import os
import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path

from cord.kinetic.streamer import KineticStreamer, INPUT_KEYBOARD, INPUT_MOUSE, KEYEVENTF_UNICODE
from cord.kinetic.evolution import KineticEvolution, AppLatencyProfile, ReflexMacro
from cord.kinetic.reflex import KineticReflexEngine
from cord.kinetic.engine import KineticEngine
from cord.tools.computer.kinetic_tool import KineticActTool
from cord.tools.computer.computer_act import ComputerActTool
from cord.tools import get_default_tools
from cord.core.modes import MODE_PROFILES, OperationalMode


def test_kinetic_streamer_compilation():
    """Verifies that streamer compiles keystrokes, unicode chars, and mouse clicks into C structs."""
    streamer = KineticStreamer()

    # 1. Atomic Keystroke
    down, up = streamer.compile_keystroke_packet(0x41)  # 'A'
    assert down.type == INPUT_KEYBOARD
    assert up.type == INPUT_KEYBOARD
    assert down.ii.ki.wVk == 0x41
    assert up.ii.ki.wVk == 0x41

    # 2. Atomic Unicode char
    d_u, u_u = streamer.compile_unicode_packet("x")
    assert d_u.type == INPUT_KEYBOARD
    assert d_u.ii.ki.wScan == ord("x")
    assert d_u.ii.ki.dwFlags == KEYEVENTF_UNICODE

    # 3. Full Text Packet Compilation
    packets = streamer.compile_text_packet("Hello\nWorld")
    assert len(packets) == (len("Hello") + 1 + len("World")) * 2

    # 4. Mouse click packet
    l_down, l_up = streamer.compile_click_packet("left")
    assert l_down.type == INPUT_MOUSE
    assert l_up.type == INPUT_MOUSE

    r_down, r_up = streamer.compile_click_packet("right")
    assert r_down.type == INPUT_MOUSE
    assert r_up.type == INPUT_MOUSE


def test_kinetic_evolution_adaptation(tmp_path):
    """Verifies that latency profiles auto-tune down with successes and back off on failures."""
    db_path = tmp_path / "test_evolution.json"
    evo = KineticEvolution(storage_path=db_path)

    prof = evo.get_profile("notepad")
    initial_delay = prof.typing_delay_ms
    assert initial_delay == 2.0

    # 3 consecutive successes trigger optimization
    evo.record_action_batch("notepad", 10, elapsed_ms=5.0, success=True)
    evo.record_action_batch("notepad", 10, elapsed_ms=4.0, success=True)
    evo.record_action_batch("notepad", 10, elapsed_ms=3.0, success=True)

    assert prof.typing_delay_ms < initial_delay
    assert prof.success_count == 3
    assert evo.total_time_saved_sec > 0.0

    # Failure penalizes and restores safety margin
    reduced_delay = prof.typing_delay_ms
    evo.record_action_batch("notepad", 10, elapsed_ms=5.0, success=False)
    assert prof.failure_count == 1
    assert prof.typing_delay_ms > reduced_delay

    # Generation counter increments every 50 actions
    for _ in range(5):
        evo.record_action_batch("notepad", 10, elapsed_ms=3.0, success=True)
    assert evo.generation >= 2

    # Test stats export
    stats = evo.get_stats()
    assert stats["generation"] >= 2
    assert "notepad" in stats["profiles"]
    assert stats["total_actions_dispatched"] >= 80

    # Persistence verification
    assert db_path.exists()
    loaded_data = json.loads(db_path.read_text(encoding="utf-8"))
    assert loaded_data["generation"] >= 2


def test_kinetic_reflex_engine():
    """Verifies built-in reflexes and dynamic reflex macro synthesis."""
    reflex_eng = KineticReflexEngine()

    # Built-in reflexes
    save_macro = reflex_eng.resolve("save")
    assert save_macro is not None
    assert save_macro.name == "save"
    assert save_macro.actions[0]["hotkey"] == "ctrl+s"

    copy_macro = reflex_eng.resolve("copy text")
    assert copy_macro is not None
    assert copy_macro.name == "copy"

    undo_macro = reflex_eng.resolve("undo")
    assert undo_macro is not None
    assert undo_macro.actions[0]["hotkey"] == "ctrl+z"

    # Dynamic synthesis
    new_macro = reflex_eng.learn_chain(
        name="submit_form",
        intent="Focus submit button and hit enter",
        actions=[{"action": "click", "x": 500, "y": 600}, {"action": "key", "key": "enter"}],
    )
    assert new_macro.name == "submit_form"

    resolved = reflex_eng.resolve("submit")
    assert resolved is not None
    assert resolved.name == "submit_form"
    assert len(resolved.actions) == 2


def test_kinetic_engine_execution(monkeypatch, tmp_path):
    """Verifies atomic click_and_type, burst_type, and batch execution logic."""
    engine = KineticEngine()
    engine.evolution = KineticEvolution(storage_path=tmp_path / "evo.json")

    # Mock low-level OS calls
    monkeypatch.setattr("cord.kinetic.engine._activate_window_at", lambda x, y: None)
    monkeypatch.setattr("cord.kinetic.engine._send_mouse_event", lambda flags, data=0: None)
    monkeypatch.setattr("cord.kinetic.engine.press_virtual_key", lambda vk: None)
    monkeypatch.setattr("cord.kinetic.engine.release_virtual_key", lambda vk: None)
    monkeypatch.setattr(engine.streamer, "dispatch_packet_batch", lambda pkts: len(pkts))

    # 1. Burst type
    res = engine.burst_type("Autonomous CORD Automation")
    assert res["success"] is True
    assert res["characters_typed"] == len("Autonomous CORD Automation")
    assert res["packets_sent"] > 0

    # 2. Click and type
    monkeypatch.setattr(engine, "move_cursor_smooth", lambda x, y, max_time_ms=15.0: None)
    res = engine.click_and_type(300, 400, "search query", press_enter=True)
    assert res["success"] is True
    assert res["coords"] == (300, 400)
    assert res["characters"] == len("search query")
    assert "faster" in res["speed_multiplier"]

    # 3. Reflex execution
    res = engine.execute_reflex("save")
    assert res["success"] is True
    assert res["reflex"] == "save"

    # 4. Batch execution
    batch_steps = [
        {"action": "click", "x": 100, "y": 200},
        {"action": "type", "text": "hello"},
        {"action": "key", "key": "enter"},
    ]
    res = engine.execute_batch(batch_steps)
    assert res["success"] is True
    assert res["total_steps"] == 3
    assert res["completed_steps"] == 3


@pytest.mark.asyncio
async def test_kinetic_act_tool(monkeypatch, tmp_path):
    """Verifies KineticActTool tool schema and asynchronous action dispatch."""
    tool = KineticActTool()
    assert tool.name == "kinetic_act"
    assert "click_and_type" in tool.parameters["properties"]["action"]["enum"]
    assert "burst_type" in tool.parameters["properties"]["action"]["enum"]
    assert "burst_batch" in tool.parameters["properties"]["action"]["enum"]
    assert "reflex" in tool.parameters["properties"]["action"]["enum"]
    assert "stats" in tool.parameters["properties"]["action"]["enum"]

    # Registered in default tools
    tools = get_default_tools()
    tool_names = {t.name for t in tools}
    assert "kinetic_act" in tool_names

    # Present in COMPUTER and CODER mode tool filters
    assert "kinetic_act" in MODE_PROFILES[OperationalMode.COMPUTER].tool_filter
    assert "kinetic_act" in MODE_PROFILES[OperationalMode.CODER].tool_filter

    # Mock engine execution
    with patch("cord.tools.computer.kinetic_tool.kinetic_engine") as mock_engine:
        mock_engine.click_and_type.return_value = {
            "success": True,
            "elapsed_ms": 12.5,
            "speed_multiplier": "120x faster",
            "characters": 10,
        }
        mock_engine.burst_type.return_value = {
            "success": True,
            "elapsed_ms": 2.1,
            "characters_typed": 10,
            "app_profile": "desktop",
            "learned_cadence_ms": 0.8,
        }
        mock_engine.execute_batch.return_value = {
            "success": True,
            "total_steps": 2,
            "completed_steps": 2,
            "elapsed_ms": 8.0,
            "evolution_generation": 3,
            "total_time_saved_sec": 45.2,
        }
        mock_engine.execute_reflex.return_value = {
            "success": True,
            "reflex": "save",
            "intent": "Save file",
            "steps": 1,
            "elapsed_ms": 1.5,
        }
        mock_engine.evolution.get_stats.return_value = {
            "generation": 3,
            "total_actions_dispatched": 140,
            "total_time_saved_sec": 52.3,
            "total_profiles": 2,
            "total_reflexes": 8,
        }

        # 1. click_and_type
        res = await tool.execute(action="click_and_type", x=150, y=250, text="test input")
        assert res.success is True
        assert "120x faster" in res.output

        # 2. burst_type
        res = await tool.execute(action="burst_type", text="test input")
        assert res.success is True
        assert "micro-packets" in res.output

        # 3. burst_batch
        res = await tool.execute(
            action="burst_batch",
            steps=[{"action": "click", "x": 10, "y": 20}, {"action": "key", "key": "enter"}],
        )
        assert res.success is True
        assert "2/2 steps executed" in res.output

        # 4. reflex
        res = await tool.execute(action="reflex", reflex_name="save")
        assert res.success is True
        assert "reflex 'save'" in res.output

        # 5. stats
        res = await tool.execute(action="stats")
        assert res.success is True
        assert "Gen 3" in res.output


@pytest.mark.asyncio
async def test_computer_act_with_kinetic_enhancements(monkeypatch):
    """Verifies ComputerActTool integration with burst_type and reflex actions."""
    act = ComputerActTool()

    with patch("cord.tools.computer.computer_act.kinetic_engine") as mock_engine:
        mock_engine.burst_type.return_value = {
            "success": True,
            "characters_typed": 15,
            "elapsed_ms": 3.2,
        }
        mock_engine.execute_reflex.return_value = {
            "success": True,
            "reflex": "copy",
            "elapsed_ms": 1.1,
        }

        # Test burst_type action in computer_act
        res = await act.execute(action="burst_type", text="Hello from CORD")
        assert res.success is True
        assert "KINETIC burst_type completed" in res.output

        # Test reflex action in computer_act
        res = await act.execute(action="reflex", reflex_name="copy")
        assert res.success is True
        assert "KINETIC reflex 'copy' executed" in res.output
