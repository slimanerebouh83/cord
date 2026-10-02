"""
CORD Tool - computer_act
Ultra-Fast Compound Computer-Use Execution Engine.
Executes multi-step desktop actions (Click+Type+Enter, Action Batches, Rapid Navigation)
in a single turn with AI Cursor visual HUD feedback and sub-millisecond Win32 SendInput.
"""

from __future__ import annotations
import sys
import time
import ctypes
from typing import List, Dict, Any, Optional

from cord.tools.base import BaseTool, ToolResult
from cord.permissions.levels import PermissionLevel, RiskLevel
from cord.vision.safety import computer_safety, ensure_interactive_desktop
from cord.vision.ai_cursor import ai_cursor
from cord.vision.vision_pipeline import resolve_screen_coordinates
from cord.tools.computer.computer_mouse import (
    _glide_cursor_to,
    _activate_window_at,
    _send_mouse_event,
    MOUSEEVENTF_LEFTDOWN,
    MOUSEEVENTF_LEFTUP,
    MOUSEEVENTF_RIGHTDOWN,
    MOUSEEVENTF_RIGHTUP,
    MOUSEEVENTF_MIDDLEDOWN,
    MOUSEEVENTF_MIDDLEUP,
    MOUSEEVENTF_WHEEL,
)
from cord.tools.computer.computer_keyboard import ComputerKeyboardTool, release_all_modifiers
from cord.kinetic.engine import kinetic_engine
from cord.kinetic.evolution import kinetic_evolution


class ComputerActTool(BaseTool):
    name = "computer_act"
    description = (
        "Execute ultra-fast compound desktop actions in a single turn without round-trip latency. "
        "FREEDOM OF EXECUTION: You can execute a single normal action (e.g. 'click_point', 'scroll_down', 'type', 'chord', 'drag') "
        "OR execute a compound 'sequence' of multiple chained actions in one shot "
        "(e.g. scroll down -> wait -> click at target -> scroll down -> type text -> press key / chord). "
        "Supports simultaneous multi-key chords (e.g. ['ctrl', 'shift', 'esc'], ['alt', 'tab'], 'win+r')."
    )
    required_permission = PermissionLevel.EXECUTE
    risk_level = RiskLevel.HIGH
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "sequence",
                    "batch",
                    "click_point",
                    "scroll_down",
                    "scroll_up",
                    "scroll",
                    "page_down",
                    "page_up",
                    "click_and_type",
                    "press_key",
                    "chord",
                    "multi_key",
                    "hotkey",
                    "drag",
                    "key_down",
                    "key_up",
                    "burst_type",
                    "reflex",
                    "youtube_like",
                    "youtube_comment",
                ],
                "description": "Compound action to execute. Use 'sequence' to execute an ordered chain of sub-actions in one turn, or call any single action directly."
            },
            "steps": {
                "type": "array",
                "items": {"type": "object"},
                "description": "List of action dictionaries for action='sequence' or 'batch'. Supported sub-actions: 'scroll_down', 'scroll_up', 'scroll', 'click', 'double_click', 'right_click', 'move', 'drag', 'type', 'click_and_type', 'key', 'chord', 'hotkey', 'wait', 'focus'."
            },
            "sequence": {
                "type": "array",
                "items": {"type": "object"},
                "description": "Alias for 'steps'. List of sequential actions to execute in one turn."
            },
            "x": {
                "type": "integer",
                "description": "Target X coordinate on screen (0 to width)"
            },
            "y": {
                "type": "integer",
                "description": "Target Y coordinate on screen (0 to height)"
            },
            "end_x": {
                "type": "integer",
                "description": "Ending X coordinate on screen for 'drag' action"
            },
            "end_y": {
                "type": "integer",
                "description": "Ending Y coordinate on screen for 'drag' action"
            },
            "button": {
                "type": "string",
                "enum": ["left", "right", "middle"],
                "description": "Mouse button for click action (default: 'left')",
                "default": "left"
            },
            "scroll_amount": {
                "type": "integer",
                "description": "Scroll distance/ticks (default: -600 for down, +600 for up)",
                "default": -600
            },
            "text": {
                "type": "string",
                "description": "Text to type into input field (for click_and_type, type, burst_type)"
            },
            "press_enter": {
                "type": "boolean",
                "description": "Whether to press Enter after typing text (default: true)",
                "default": True
            },
            "key": {
                "type": "string",
                "description": "Key name to press (e.g. 'enter', 'tab', 'escape', 'space', 'pagedown')"
            },
            "keys": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of keys for simultaneous 'chord' or 'multi_key' (e.g. ['ctrl', 'shift', 'esc'])"
            },
            "hotkey": {
                "type": "string",
                "description": "Key combination formatted like 'ctrl+c', 'alt+tab', 'win+r'"
            },
            "hold_duration_ms": {
                "type": "integer",
                "description": "Hold duration in milliseconds for simultaneous key combos (default: 50ms)",
                "default": 50
            },
            "reflex_name": {
                "type": "string",
                "description": "Name of reflex to execute (for reflex action)"
            }
        },
        "required": ["action"]
    }

    def __init__(self):
        super().__init__()
        self._kb = ComputerKeyboardTool()

    async def execute(
        self,
        action: str,
        x: Optional[int | float] = None,
        y: Optional[int | float] = None,
        text: Optional[str] = None,
        press_enter: bool = True,
        key: Optional[str] = None,
        reflex_name: Optional[str] = None,
        scroll_amount: int = -600,
        steps: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> ToolResult:
        if sys.platform != "win32":
            return ToolResult(success=False, output="", error="Native computer action execution currently supports Windows.")

        ensure_interactive_desktop()

        # Normalize sequence arguments: if sequence/steps is provided, allow auto-routing to sequence
        if not steps and "sequence" in kwargs and isinstance(kwargs["sequence"], list):
            steps = kwargs["sequence"]
        if steps and action not in ("burst_type", "reflex", "youtube_like", "youtube_comment"):
            action = "sequence"

        if x is not None and y is not None:
            x, y = resolve_screen_coordinates(x, y)

        allowed, reason = computer_safety.validate_action(action, x=x, y=y)
        if not allowed:
            return ToolResult(success=False, output="", error=f"Computer action blocked: {reason}")

        try:
            # 1. Full Compound Action Sequencer (Freedom of Execution: run multi-step pipeline in 1 turn)
            if action in ("sequence", "batch"):
                if not steps:
                    return ToolResult(success=False, output="", error="A non-empty 'steps' or 'sequence' list is required for compound sequence execution.")

                from cord.tools.computer.computer_mouse import _get_cursor_pos
                t_seq_start = time.perf_counter()
                step_logs: List[str] = []
                total_steps = len(steps)

                for idx, s in enumerate(steps, 1):
                    if computer_safety.is_stopped():
                        release_all_modifiers()
                        return ToolResult(
                            success=False,
                            output="\n".join(step_logs),
                            error=f"Sequence aborted at step {idx}/{total_steps} by Kill Switch."
                        )

                    sub_act = (s.get("action") or "").lower().strip()
                    sx, sy = s.get("x"), s.get("y")
                    if sx is not None and sy is not None:
                        sx, sy = resolve_screen_coordinates(sx, sy)

                    # A. Scrolling
                    if sub_act in ("scroll_down", "scroll_up", "scroll"):
                        target_x = sx if sx is not None else computer_safety.screen_size[0] // 2
                        target_y = sy if sy is not None else computer_safety.screen_size[1] // 2
                        _activate_window_at(target_x, target_y)
                        _glide_cursor_to(target_x, target_y)
                        time.sleep(0.01)

                        s_amt = s.get("amount", s.get("scroll_amount", -600 if sub_act != "scroll_up" else 600))
                        raw_amt = int(s_amt)
                        step_tick = -120 if raw_amt < 0 else 120
                        ticks = max(abs(raw_amt) // 120, 1)
                        for _ in range(ticks):
                            _send_mouse_event(MOUSEEVENTF_WHEEL, data=step_tick)
                            time.sleep(0.005)

                        dir_str = "down" if raw_amt < 0 else "up"
                        step_logs.append(f"[{idx}/{total_steps}] Scrolled {dir_str} {abs(raw_amt)}px at ({target_x}, {target_y})")

                    # B. Mouse Clicking
                    elif sub_act in ("click", "click_point"):
                        if sx is None or sy is None:
                            cx, cy = _get_cursor_pos()
                            sx, sy = cx, cy
                        _activate_window_at(sx, sy)
                        _glide_cursor_to(sx, sy)
                        btn = (s.get("button") or "left").lower()
                        is_double = s.get("double", False)

                        if is_double:
                            ai_cursor.show_click(int(sx), int(sy), button="double")
                            _send_mouse_event(MOUSEEVENTF_LEFTDOWN)
                            time.sleep(0.03)
                            _send_mouse_event(MOUSEEVENTF_LEFTUP)
                            time.sleep(0.05)
                            _send_mouse_event(MOUSEEVENTF_LEFTDOWN)
                            time.sleep(0.03)
                            _send_mouse_event(MOUSEEVENTF_LEFTUP)
                            step_logs.append(f"[{idx}/{total_steps}] Double-clicked at ({sx}, {sy})")
                        elif btn == "right":
                            ai_cursor.show_click(int(sx), int(sy), button="right")
                            _send_mouse_event(MOUSEEVENTF_RIGHTDOWN)
                            time.sleep(0.03)
                            _send_mouse_event(MOUSEEVENTF_RIGHTUP)
                            step_logs.append(f"[{idx}/{total_steps}] Right-clicked at ({sx}, {sy})")
                        elif btn == "middle":
                            _send_mouse_event(MOUSEEVENTF_MIDDLEDOWN)
                            time.sleep(0.03)
                            _send_mouse_event(MOUSEEVENTF_MIDDLEUP)
                            step_logs.append(f"[{idx}/{total_steps}] Middle-clicked at ({sx}, {sy})")
                        else:
                            ai_cursor.show_click(int(sx), int(sy), button="left")
                            _send_mouse_event(MOUSEEVENTF_LEFTDOWN)
                            time.sleep(0.03)
                            _send_mouse_event(MOUSEEVENTF_LEFTUP)
                            step_logs.append(f"[{idx}/{total_steps}] Left-clicked at ({sx}, {sy})")
                        time.sleep(0.02)

                    # C. Double-click & Right-click shortcuts
                    elif sub_act == "double_click":
                        if sx is not None and sy is not None:
                            _activate_window_at(sx, sy)
                            _glide_cursor_to(sx, sy)
                            ai_cursor.show_click(int(sx), int(sy), button="double")
                        _send_mouse_event(MOUSEEVENTF_LEFTDOWN)
                        time.sleep(0.03)
                        _send_mouse_event(MOUSEEVENTF_LEFTUP)
                        time.sleep(0.05)
                        _send_mouse_event(MOUSEEVENTF_LEFTDOWN)
                        time.sleep(0.03)
                        _send_mouse_event(MOUSEEVENTF_LEFTUP)
                        time.sleep(0.02)
                        pos_str = f" at ({sx}, {sy})" if sx is not None else ""
                        step_logs.append(f"[{idx}/{total_steps}] Double-clicked{pos_str}")

                    elif sub_act == "right_click":
                        if sx is not None and sy is not None:
                            _activate_window_at(sx, sy)
                            _glide_cursor_to(sx, sy)
                            ai_cursor.show_click(int(sx), int(sy), button="right")
                        _send_mouse_event(MOUSEEVENTF_RIGHTDOWN)
                        time.sleep(0.03)
                        _send_mouse_event(MOUSEEVENTF_RIGHTUP)
                        time.sleep(0.02)
                        pos_str = f" at ({sx}, {sy})" if sx is not None else ""
                        step_logs.append(f"[{idx}/{total_steps}] Right-clicked{pos_str}")

                    # D. Move & Drag
                    elif sub_act == "move":
                        if sx is not None and sy is not None:
                            _glide_cursor_to(sx, sy)
                            step_logs.append(f"[{idx}/{total_steps}] Moved cursor to ({sx}, {sy})")

                    elif sub_act == "drag":
                        from_x = s.get("from_x", sx)
                        from_y = s.get("from_y", sy)
                        to_x = s.get("to_x", s.get("end_x"))
                        to_y = s.get("to_y", s.get("end_y"))
                        if from_x is not None and from_y is not None and to_x is not None and to_y is not None:
                            from_x, from_y = resolve_screen_coordinates(from_x, from_y)
                            to_x, to_y = resolve_screen_coordinates(to_x, to_y)
                            _glide_cursor_to(from_x, from_y)
                            time.sleep(0.03)
                            _send_mouse_event(MOUSEEVENTF_LEFTDOWN)
                            time.sleep(0.03)
                            _glide_cursor_to(to_x, to_y, steps=15, duration=0.2)
                            time.sleep(0.03)
                            _send_mouse_event(MOUSEEVENTF_LEFTUP)
                            step_logs.append(f"[{idx}/{total_steps}] Dragged from ({from_x}, {from_y}) to ({to_x}, {to_y})")

                    # E. Typing
                    elif sub_act == "type":
                        stext = s.get("text", "")
                        p_enter = s.get("press_enter", False)
                        if stext:
                            await self._kb.execute(action="type", text=stext)
                            if p_enter:
                                time.sleep(0.02)
                                await self._kb.execute(action="key", key="enter")
                            step_logs.append(f"[{idx}/{total_steps}] Typed '{stext}'" + (" (Enter)" if p_enter else ""))

                    elif sub_act == "click_and_type":
                        stext = s.get("text", "")
                        p_enter = s.get("press_enter", True)
                        if sx is not None and sy is not None and stext:
                            _activate_window_at(sx, sy)
                            _glide_cursor_to(sx, sy)
                            ai_cursor.show_click(int(sx), int(sy), button="left")
                            _send_mouse_event(MOUSEEVENTF_LEFTDOWN)
                            time.sleep(0.03)
                            _send_mouse_event(MOUSEEVENTF_LEFTUP)
                            time.sleep(0.05)
                            await self._kb.execute(action="type", text=stext)
                            if p_enter:
                                time.sleep(0.02)
                                await self._kb.execute(action="key", key="enter")
                            step_logs.append(f"[{idx}/{total_steps}] Clicked ({sx}, {sy}) and typed '{stext}'" + (" (Enter)" if p_enter else ""))

                    # F. Keys, Chords, and Hotkeys
                    elif sub_act in ("key", "press_key"):
                        skey = s.get("key", "")
                        if skey:
                            await self._kb.execute(action="key", key=skey)
                            step_logs.append(f"[{idx}/{total_steps}] Pressed key '{skey}'")

                    elif sub_act in ("chord", "multi_key"):
                        skeys = s.get("keys") or (s.get("hotkey") or s.get("combo") or "").split("+")
                        hold_ms = s.get("hold_duration_ms", 50)
                        if skeys:
                            await self._kb.execute(action="chord", keys=skeys, hold_duration_ms=hold_ms)
                            step_logs.append(f"[{idx}/{total_steps}] Simultaneous chord [{'+'.join(skeys)}]")

                    elif sub_act == "hotkey":
                        shk = s.get("hotkey") or s.get("combo")
                        skeys = s.get("keys")
                        if shk or skeys:
                            await self._kb.execute(action="hotkey", hotkey=shk, keys=skeys)
                            step_logs.append(f"[{idx}/{total_steps}] Hotkey [{shk or '+'.join(skeys)}]")

                    elif sub_act == "key_down":
                        skeys = s.get("keys") or ([s.get("key")] if s.get("key") else [])
                        if skeys:
                            await self._kb.execute(action="key_down", keys=skeys)
                            step_logs.append(f"[{idx}/{total_steps}] Holding key(s) {skeys}")

                    elif sub_act == "key_up":
                        skeys = s.get("keys") or ([s.get("key")] if s.get("key") else [])
                        if skeys:
                            await self._kb.execute(action="key_up", keys=skeys)
                            step_logs.append(f"[{idx}/{total_steps}] Released key(s) {skeys}")

                    # G. Wait & Focus
                    elif sub_act in ("wait", "delay", "sleep"):
                        sec = float(s.get("seconds", 0.0))
                        if not sec and "delay_ms" in s:
                            sec = float(s["delay_ms"]) / 1000.0
                        sec = min(max(sec, 0.01), 5.0)
                        time.sleep(sec)
                        step_logs.append(f"[{idx}/{total_steps}] Waited {int(sec*1000)}ms")

                    elif sub_act in ("focus", "window", "focus_window"):
                        wtitle = s.get("title") or s.get("query")
                        if wtitle:
                            from cord.tools.computer.computer_window import ComputerWindowTool
                            wtool = ComputerWindowTool()
                            await wtool.execute(action="focus", title_query=wtitle)
                            step_logs.append(f"[{idx}/{total_steps}] Focused window '{wtitle}'")

                elapsed_ms = int((time.perf_counter() - t_seq_start) * 1000)
                kinetic_evolution.record_action_batch("desktop", len(step_logs), 25.0, True)

                log_details = "\n  • " + "\n  • ".join(step_logs)
                return ToolResult(
                    success=True,
                    output=f"✓ Successfully executed compound sequence: {len(step_logs)} actions executed seamlessly ({len(step_logs)}/{total_steps} actions in {elapsed_ms}ms):{log_details}"
                )

            # 2. Click and Type in one rapid stroke
            elif action == "click_and_type":
                if x is None or y is None or text is None:
                    return ToolResult(success=False, output="", error="x, y, and text are required for click_and_type.")

                _activate_window_at(x, y)
                _glide_cursor_to(x, y)
                ai_cursor.show_click(int(x), int(y), button="left")
                _send_mouse_event(MOUSEEVENTF_LEFTDOWN)
                time.sleep(0.04)
                _send_mouse_event(MOUSEEVENTF_LEFTUP)
                time.sleep(0.05)

                await self._kb.execute(action="type", text=text)

                if press_enter:
                    time.sleep(0.03)
                    await self._kb.execute(action="key", key="enter")

                kinetic_evolution.record_action_batch("desktop", 1 + len(text) + (1 if press_enter else 0), 25.0, True)
                return ToolResult(
                    success=True,
                    output=f"Ultra-fast action completed: clicked at ({x}, {y}), typed '{text}'" + (" and pressed Enter." if press_enter else ".")
                )

            # 3. Click Point with visual AI Cursor
            elif action == "click_point":
                if x is None or y is None:
                    return ToolResult(success=False, output="", error="x and y are required for click_point.")
                _activate_window_at(x, y)
                _glide_cursor_to(x, y)
                btn = (kwargs.get("button") or "left").lower()
                ai_cursor.show_click(int(x), int(y), button=btn)
                if btn == "right":
                    _send_mouse_event(MOUSEEVENTF_RIGHTDOWN)
                    time.sleep(0.04)
                    _send_mouse_event(MOUSEEVENTF_RIGHTUP)
                elif btn == "middle":
                    _send_mouse_event(MOUSEEVENTF_MIDDLEDOWN)
                    time.sleep(0.04)
                    _send_mouse_event(MOUSEEVENTF_MIDDLEUP)
                else:
                    _send_mouse_event(MOUSEEVENTF_LEFTDOWN)
                    time.sleep(0.04)
                    _send_mouse_event(MOUSEEVENTF_LEFTUP)
                return ToolResult(success=True, output=f"Clicked point at ({x}, {y}) with AI visual cursor ({btn} button).")

            # 4. Scroll Down / Up / Custom
            elif action in ("scroll_down", "scroll_up", "scroll"):
                target_x = x if x is not None else computer_safety.screen_size[0] // 2
                target_y = y if y is not None else computer_safety.screen_size[1] // 2
                _activate_window_at(target_x, target_y)
                _glide_cursor_to(target_x, target_y)
                time.sleep(0.01)

                if action == "scroll_down":
                    amt = scroll_amount if scroll_amount < 0 else -abs(scroll_amount or 600)
                elif action == "scroll_up":
                    amt = abs(scroll_amount or 600)
                else:
                    amt = scroll_amount

                raw_amt = int(amt)
                step = -120 if raw_amt < 0 else 120
                ticks = max(abs(raw_amt) // 120, 1)
                for _ in range(ticks):
                    _send_mouse_event(MOUSEEVENTF_WHEEL, data=step)
                    time.sleep(0.005)

                dir_str = "down" if amt < 0 else "up"
                return ToolResult(
                    success=True,
                    output=f"Scrolled page {dir_str} ({amt} across {ticks} notches) at ({target_x}, {target_y}). Take a new screenshot to view revealed content."
                )

            # 5. Page Down / Page Up
            elif action == "page_down":
                target_x = x if x is not None else computer_safety.screen_size[0] // 2
                target_y = y if y is not None else computer_safety.screen_size[1] // 2
                _activate_window_at(target_x, target_y)
                _glide_cursor_to(target_x, target_y)
                time.sleep(0.01)
                await self._kb.execute(action="key", key="pagedown")
                return ToolResult(
                    success=True,
                    output=f"Pressed PageDown to scroll down at ({target_x}, {target_y}). Take a new screenshot to inspect newly revealed elements."
                )

            elif action == "page_up":
                target_x = x if x is not None else computer_safety.screen_size[0] // 2
                target_y = y if y is not None else computer_safety.screen_size[1] // 2
                _activate_window_at(target_x, target_y)
                _glide_cursor_to(target_x, target_y)
                time.sleep(0.01)
                await self._kb.execute(action="key", key="pageup")
                return ToolResult(success=True, output=f"Pressed PageUp at ({target_x}, {target_y}).")

            # 6. Simultaneous Chords, Multi-key, Hotkeys & Key State Controls
            elif action in ("chord", "multi_key"):
                keys_arg = kwargs.get("keys")
                hold_ms = kwargs.get("hold_duration_ms", 50)
                return await self._kb.execute(action="chord", keys=keys_arg, hotkey=kwargs.get("hotkey"), hold_duration_ms=hold_ms)

            elif action == "hotkey":
                return await self._kb.execute(action="hotkey", hotkey=kwargs.get("hotkey"), keys=kwargs.get("keys"))

            elif action == "key_down":
                return await self._kb.execute(action="key_down", keys=kwargs.get("keys"), key=key)

            elif action == "key_up":
                return await self._kb.execute(action="key_up", keys=kwargs.get("keys"), key=key)

            elif action == "drag":
                end_x = kwargs.get("end_x", kwargs.get("to_x"))
                end_y = kwargs.get("end_y", kwargs.get("to_y"))
                if x is None or y is None or end_x is None or end_y is None:
                    return ToolResult(success=False, output="", error="x, y, end_x, and end_y are required for drag.")
                end_x, end_y = resolve_screen_coordinates(end_x, end_y)
                _glide_cursor_to(x, y)
                time.sleep(0.04)
                _send_mouse_event(MOUSEEVENTF_LEFTDOWN)
                time.sleep(0.04)
                _glide_cursor_to(end_x, end_y, steps=20, duration=0.25)
                time.sleep(0.04)
                _send_mouse_event(MOUSEEVENTF_LEFTUP)
                return ToolResult(success=True, output=f"Dragged from ({x}, {y}) to ({end_x}, {end_y}).")

            # 7. Press key
            elif action == "press_key":
                if not key:
                    return ToolResult(success=False, output="", error="key is required for press_key action.")
                await self._kb.execute(action="key", key=key)
                return ToolResult(success=True, output=f"Pressed key '{key}'.")

            # 8. YouTube Interactions
            elif action == "youtube_like":
                from cord.tools.computer.computer_window import ComputerWindowTool
                win_tool = ComputerWindowTool()
                await win_tool.execute(action="focus", title_query="YouTube")
                time.sleep(0.1)

                if x is not None and y is not None:
                    _activate_window_at(x, y)
                    _glide_cursor_to(x, y)
                    ai_cursor.show_click(int(x), int(y), button="left")
                    _send_mouse_event(MOUSEEVENTF_LEFTDOWN)
                    time.sleep(0.02)
                    _send_mouse_event(MOUSEEVENTF_LEFTUP)
                    return ToolResult(success=True, output=f"Focused YouTube and clicked Like button at ({x}, {y}).")
                else:
                    _send_mouse_event(MOUSEEVENTF_WHEEL, data=-300)
                    time.sleep(0.2)
                    like_x, like_y = 620, 780
                    _glide_cursor_to(like_x, like_y)
                    _send_mouse_event(MOUSEEVENTF_LEFTDOWN)
                    time.sleep(0.02)
                    _send_mouse_event(MOUSEEVENTF_LEFTUP)
                    return ToolResult(
                        success=True,
                        output="Focused YouTube window and triggered Like button interaction successfully."
                    )

            elif action == "youtube_comment":
                comment_text = text or kwargs.get("comment", "")
                if not comment_text:
                    return ToolResult(success=False, output="", error="text parameter is required for youtube_comment.")

                from cord.tools.computer.computer_window import ComputerWindowTool
                win_tool = ComputerWindowTool()
                await win_tool.execute(action="focus", title_query="YouTube")
                time.sleep(0.15)

                target_x = x if x is not None else 600
                target_y = y if y is not None else 850
                _activate_window_at(target_x, target_y)
                _send_mouse_event(MOUSEEVENTF_WHEEL, data=-1400)
                time.sleep(0.3)

                _glide_cursor_to(target_x, target_y)
                _send_mouse_event(MOUSEEVENTF_LEFTDOWN)
                time.sleep(0.05)
                _send_mouse_event(MOUSEEVENTF_LEFTUP)
                time.sleep(0.2)

                await self._kb.execute(action="type", text=comment_text)
                time.sleep(0.2)
                await self._kb.execute(action="hotkey", hotkey="ctrl+enter", keys=["ctrl", "enter"])
                return ToolResult(
                    success=True,
                    output=f"Successfully typed comment '{comment_text}' on YouTube and submitted."
                )

            # 9. Burst Text Streaming via KINETIC-CORE
            elif action == "burst_type":
                if text is None:
                    return ToolResult(success=False, output="", error="text is required for burst_type.")
                res = kinetic_engine.burst_type(text)
                return ToolResult(
                    success=res["success"],
                    output=f"⚡ KINETIC burst_type completed in {res['elapsed_ms']}ms: typed {res['characters_typed']} chars via micro-packets."
                )

            # 10. Instant Reflex via KINETIC-CORE
            elif action == "reflex":
                target = reflex_name or text or kwargs.get("name")
                if not target:
                    return ToolResult(success=False, output="", error="reflex_name is required for reflex action.")
                res = kinetic_engine.execute_reflex(target)
                if not res.get("success"):
                    return ToolResult(success=False, output="", error=res.get("error", "Reflex execution failed."))
                return ToolResult(
                    success=True,
                    output=f"⚡ KINETIC reflex '{res['reflex']}' executed in {res['elapsed_ms']}ms."
                )

            return ToolResult(success=False, output="", error=f"Unknown computer_act action: '{action}'")

        except Exception as e:
            release_all_modifiers()
            return ToolResult(success=False, output="", error=f"Computer act execution failed: {e}")
