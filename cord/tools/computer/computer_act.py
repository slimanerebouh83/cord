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
    MOUSEEVENTF_WHEEL,
)
from cord.tools.computer.computer_keyboard import ComputerKeyboardTool
from cord.kinetic.engine import kinetic_engine
from cord.kinetic.evolution import kinetic_evolution


class ComputerActTool(BaseTool):
    name = "computer_act"
    description = (
        "Execute ultra-fast compound desktop actions in a single turn without round-trip latency. "
        "Supports 'scroll_down' (scrolls page down to reveal hidden buttons/content), "
        "'scroll_up', 'scroll', 'page_down', 'click_point', 'click_and_type', 'batch', and 'youtube_like'."
    )
    required_permission = PermissionLevel.EXECUTE
    risk_level = RiskLevel.HIGH
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "click_point",
                    "scroll_down",
                    "scroll_up",
                    "scroll",
                    "page_down",
                    "page_up",
                    "click_and_type",
                    "batch",
                    "youtube_like",
                    "youtube_comment",
                    "press_key",
                    "burst_type",
                    "reflex",
                ],
                "description": "Compound action to execute. Use 'scroll_down' if target buttons/elements are not yet visible!"
            },
            "x": {
                "type": "integer",
                "description": "Target X coordinate on screen (0 to width)"
            },
            "y": {
                "type": "integer",
                "description": "Target Y coordinate on screen (0 to height)"
            },
            "scroll_amount": {
                "type": "integer",
                "description": "Scroll distance/ticks (default: -600 for down, +600 for up)",
                "default": -600
            },
            "text": {
                "type": "string",
                "description": "Text to type into input field (for click_and_type)"
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
            "reflex_name": {
                "type": "string",
                "description": "Name of reflex to execute (for reflex action)"
            },
            "steps": {
                "type": "array",
                "items": {"type": "object"},
                "description": "List of sub-actions to execute rapidly for action='batch' (e.g. [{'action': 'click', 'x': 500, 'y': 300}, {'action': 'scroll_down'}, ...])"
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

        if x is not None and y is not None:
            x, y = resolve_screen_coordinates(x, y)

        allowed, reason = computer_safety.validate_action(action, x=x, y=y)
        if not allowed:
            return ToolResult(success=False, output="", error=f"Computer action blocked: {reason}")

        try:
            # 1. Click and Type in one rapid stroke
            if action == "click_and_type":
                if x is None or y is None or text is None:
                    return ToolResult(success=False, output="", error="x, y, and text are required for click_and_type.")

                # Fast activate, glide, and click
                _activate_window_at(x, y)
                _glide_cursor_to(x, y)
                ai_cursor.show_click(int(x), int(y), button="left")
                _send_mouse_event(MOUSEEVENTF_LEFTDOWN)
                time.sleep(0.04)  # 40ms hold time
                _send_mouse_event(MOUSEEVENTF_LEFTUP)
                time.sleep(0.05)

                # Type text with Unicode SendInput
                await self._kb.execute(action="type", text=text)

                # Optionally press enter
                if press_enter:
                    time.sleep(0.03)
                    await self._kb.execute(action="key", key="enter")

                kinetic_evolution.record_action_batch("desktop", 1 + len(text) + (1 if press_enter else 0), 25.0, True)

                return ToolResult(
                    success=True,
                    output=f"Ultra-fast action completed: clicked at ({x}, {y}), typed '{text}'" + (" and pressed Enter." if press_enter else ".")
                )

            # 2. Click Point with visual AI Cursor
            elif action == "click_point":
                if x is None or y is None:
                    return ToolResult(success=False, output="", error="x and y are required for click_point.")
                _activate_window_at(x, y)
                _glide_cursor_to(x, y)
                ai_cursor.show_click(int(x), int(y), button="left")
                _send_mouse_event(MOUSEEVENTF_LEFTDOWN)
                time.sleep(0.04)  # 40ms hold time
                _send_mouse_event(MOUSEEVENTF_LEFTUP)
                return ToolResult(success=True, output=f"Clicked point at ({x}, {y}) with AI visual cursor.")

            # 3. Scroll Down / Up / Custom
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

            # 4. Page Down / Page Up
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
                return ToolResult(
                    success=True,
                    output=f"Pressed PageUp at ({target_x}, {target_y})."
                )

            # 5. YouTube Like action
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
                    # Native YouTube Web shortcut or standard Like button position
                    # Focus page and press 'l' (or click typical Like location around x=620, y=780)
                    _send_mouse_event(MOUSEEVENTF_WHEEL, data=-300)
                    time.sleep(0.2)
                    # Click like button near action bar
                    like_x, like_y = 620, 780
                    _glide_cursor_to(like_x, like_y)
                    _send_mouse_event(MOUSEEVENTF_LEFTDOWN)
                    time.sleep(0.02)
                    _send_mouse_event(MOUSEEVENTF_LEFTUP)
                    return ToolResult(
                        success=True,
                        output="Focused YouTube window and triggered Like button interaction successfully."
                    )

            # 5b. YouTube Comment action
            elif action == "youtube_comment":
                comment_text = text or kwargs.get("comment", "")
                if not comment_text:
                    return ToolResult(success=False, output="", error="text parameter is required for youtube_comment.")

                from cord.tools.computer.computer_window import ComputerWindowTool
                win_tool = ComputerWindowTool()
                await win_tool.execute(action="focus", title_query="YouTube")
                time.sleep(0.15)

                # Scroll down to reveal comments section
                target_x = x if x is not None else 600
                target_y = y if y is not None else 850
                _activate_window_at(target_x, target_y)
                _send_mouse_event(MOUSEEVENTF_WHEEL, data=-1400)
                time.sleep(0.3)

                # Click comment input box
                _glide_cursor_to(target_x, target_y)
                _send_mouse_event(MOUSEEVENTF_LEFTDOWN)
                time.sleep(0.05)
                _send_mouse_event(MOUSEEVENTF_LEFTUP)
                time.sleep(0.2)

                # Type comment text via unicode SendInput
                await self._kb.execute(action="type", text=comment_text)
                time.sleep(0.2)

                # Submit via Ctrl+Enter (YouTube native shortcut to post comment)
                await self._kb.execute(action="hotkey", hotkey="ctrl+enter", keys=["ctrl", "enter"])
                return ToolResult(
                    success=True,
                    output=f"Successfully typed comment '{comment_text}' on YouTube and submitted."
                )

            # 6. Press key
            elif action == "press_key":
                if not key:
                    return ToolResult(success=False, output="", error="key is required for press_key action.")
                await self._kb.execute(action="key", key=key)
                return ToolResult(success=True, output=f"Pressed key '{key}'.")

            # 7. Batch rapid sequence
            elif action == "batch":
                if not steps:
                    return ToolResult(success=False, output="", error="steps list is required for batch action.")

                executed_count = 0
                for s in steps:
                    sub_act = s.get("action")
                    if sub_act == "click":
                        sx, sy = s.get("x"), s.get("y")
                        if sx is not None and sy is not None:
                            _activate_window_at(sx, sy)
                            _glide_cursor_to(sx, sy)
                            ai_cursor.show_click(int(sx), int(sy), button="left")
                            _send_mouse_event(MOUSEEVENTF_LEFTDOWN)
                            time.sleep(0.02)
                            _send_mouse_event(MOUSEEVENTF_LEFTUP)
                            executed_count += 1
                    elif sub_act in ("scroll", "scroll_down", "scroll_up"):
                        sx = s.get("x") or computer_safety.screen_size[0] // 2
                        sy = s.get("y") or computer_safety.screen_size[1] // 2
                        _activate_window_at(sx, sy)
                        _glide_cursor_to(sx, sy)
                        time.sleep(0.01)
                        s_amt = s.get("amount", -600 if sub_act != "scroll_up" else 600)
                        ticks = max(abs(int(s_amt)) // 120, 1)
                        step = -120 if s_amt < 0 else 120
                        for _ in range(ticks):
                            _send_mouse_event(MOUSEEVENTF_WHEEL, data=step)
                            time.sleep(0.005)
                        executed_count += 1
                    elif sub_act == "type":
                        stext = s.get("text", "")
                        if stext:
                            await self._kb.execute(action="type", text=stext)
                            executed_count += 1
                    elif sub_act == "key":
                        skey = s.get("key", "")
                        if skey:
                            await self._kb.execute(action="key", key=skey)
                            executed_count += 1
                    elif sub_act == "wait":
                        sec = min(float(s.get("seconds", 0.1)), 3.0)
                        time.sleep(sec)
                        executed_count += 1

                kinetic_evolution.record_action_batch("desktop", executed_count, 30.0, True)

                return ToolResult(success=True, output=f"Batch execution completed: {executed_count} actions executed seamlessly.")

            # 8. Burst Text Streaming via KINETIC-CORE
            elif action == "burst_type":
                if text is None:
                    return ToolResult(success=False, output="", error="text is required for burst_type.")
                res = kinetic_engine.burst_type(text)
                return ToolResult(
                    success=res["success"],
                    output=f"⚡ KINETIC burst_type completed in {res['elapsed_ms']}ms: typed {res['characters_typed']} chars via micro-packets."
                )

            # 9. Instant Reflex via KINETIC-CORE
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
            return ToolResult(success=False, output="", error=f"Computer act execution failed: {e}")
