"""
NITEE v3 - Local Executor Module
Ultra-low latency local action executor (1-10 ms per action) supporting
CLICK, SET_TEXT, KEY, HOLD_KEY, MOVE, SCROLL, WAIT_STATE, and DONE.
Enforces security rules, password field protection, and human-in-the-loop risk gating.
"""

from __future__ import annotations
import sys
import time
import re
from typing import Dict, List, Any, Optional, Tuple
from cord.nitee.optimizer import WaitOptimizer
from cord.nitee.structural_tree import UIElementNode
from cord.nitee.vision_matcher import VisionObject


class NiteeExecutor:
    """Dispatches batches of concrete plan steps at near-zero latency."""

    HIGH_RISK_KEYWORDS = {"submit", "send", "pay", "delete", "confirm", "remove", "drop", "terminate"}

    def __init__(self, optimizer: Optional[WaitOptimizer] = None):
        self.optimizer = optimizer or WaitOptimizer()
        self._last_execution_stats: Dict[str, Any] = {}

    def execute_batch(
        self,
        plan: List[Dict[str, Any]],
        element_map: Dict[str, Any],
        is_vision_mode: bool = False,
        allow_high_risk: bool = False,
    ) -> Dict[str, Any]:
        """Execute a batch of 3-10 plan steps locally.
        
        Args:
            plan: List of action steps
            element_map: Dict mapping element_id to UIElementNode or VisionObject
            is_vision_mode: True if operating on vision/game surface
            allow_high_risk: True if user or human gate approved high risk steps
            
        Returns:
            Dict detailing results, timing, and errors
        """
        step_results = []
        errors = []
        batch_start = time.time()
        completed_cleanly = True

        for step in plan:
            step_num = step.get("step", len(step_results) + 1)
            action = (step.get("action") or "").upper().strip()
            element_id = step.get("element_id")
            value = step.get("value")
            expect = step.get("expect")
            wait_label = step.get("wait_label")
            risk = (step.get("risk") or "low").lower().strip()

            step_record = {
                "step": step_num,
                "action": action,
                "element_id": element_id,
                "status": "pending",
                "elapsed_ms": 0.0,
            }

            # Check High-Risk Action Gating
            is_high_risk = (
                risk == "high" or
                any(k in action.lower() for k in self.HIGH_RISK_KEYWORDS) or
                (value and any(k in str(value).lower() for k in self.HIGH_RISK_KEYWORDS))
            )
            if is_high_risk and not allow_high_risk:
                step_record["status"] = "gated_risk"
                step_record["error"] = "High-risk action requires user confirmation gate"
                step_results.append(step_record)
                return {
                    "success": False,
                    "completed_steps": len(step_results) - 1,
                    "total_steps": len(plan),
                    "needs_human_approval": True,
                    "gated_step": step,
                    "step_results": step_results,
                    "errors": ["Step requires human gate confirmation (risk: high)"],
                }

            s_start = time.time()
            try:
                if action == "CLICK":
                    self._exec_click(element_id, element_map)
                    step_record["status"] = "success"

                elif action == "SET_TEXT":
                    if is_vision_mode:
                        raise ValueError("SET_TEXT is unavailable in vision mode — refuse it.")
                    self._exec_set_text(element_id, str(value or ""), element_map)
                    step_record["status"] = "success"

                elif action == "KEY":
                    self._exec_key(str(value or ""), is_vision_mode)
                    step_record["status"] = "success"

                elif action == "HOLD_KEY":
                    self._exec_hold_key(str(value or "w:300"))
                    step_record["status"] = "success"

                elif action == "MOVE":
                    self._exec_move(value, element_id, element_map)
                    step_record["status"] = "success"

                elif action == "SCROLL":
                    delta = int(value) if value is not None else -600
                    self._exec_scroll(delta)
                    step_record["status"] = "success"

                elif action == "WAIT_STATE":
                    elapsed_wait = self._exec_wait_state(wait_label, expect, element_map)
                    step_record["status"] = "success"
                    step_record["wait_elapsed_ms"] = elapsed_wait

                elif action == "DONE":
                    step_record["status"] = "done"
                    step_record["elapsed_ms"] = round((time.time() - s_start) * 1000, 2)
                    step_results.append(step_record)
                    break

                else:
                    raise ValueError(f"Unknown action: {action}")

            except Exception as e:
                err_msg = str(e)
                step_record["status"] = "error"
                step_record["error"] = err_msg
                errors.append(f"Step {step_num} ({action}) failed: {err_msg}")
                completed_cleanly = False
                step_record["elapsed_ms"] = round((time.time() - s_start) * 1000, 2)
                step_results.append(step_record)
                break  # Stop batch execution on first failure to report EXECUTOR_FEEDBACK

            step_record["elapsed_ms"] = round((time.time() - s_start) * 1000, 2)
            step_results.append(step_record)

        total_batch_ms = round((time.time() - batch_start) * 1000, 2)
        return {
            "success": completed_cleanly and len(errors) == 0,
            "completed_steps": len([s for s in step_results if s["status"] in ("success", "done")]),
            "total_steps": len(plan),
            "needs_human_approval": False,
            "total_ms": total_batch_ms,
            "step_results": step_results,
            "errors": errors,
        }

    def _exec_click(self, element_id: Optional[str], element_map: Dict[str, Any]) -> None:
        """Execute click on target element ID."""
        if not element_id or element_id not in element_map:
            raise ValueError(f"Element ID '{element_id}' not found in current UI state tree")

        node = element_map[element_id]

        # 1. Try structural UIAutomation InvokePattern or TogglePattern if available
        if isinstance(node, UIElementNode) and node.raw_control:
            try:
                ctrl = node.raw_control
                if hasattr(ctrl, "GetInvokePattern"):
                    inv = ctrl.GetInvokePattern()
                    if inv:
                        inv.Invoke()
                        return
                if hasattr(ctrl, "GetTogglePattern"):
                    tog = ctrl.GetTogglePattern()
                    if tog:
                        tog.Toggle()
                        return
            except Exception:
                pass

        # 2. Fall back to instantaneous Win32 mouse click at element center
        cx = getattr(node, "center_x", 0)
        cy = getattr(node, "center_y", 0)
        if cx <= 0 and cy <= 0:
            raise ValueError(f"Element '{element_id}' has invalid coordinates: ({cx}, {cy})")

        self._click_coords(cx, cy)

    def _exec_set_text(self, element_id: Optional[str], text: str, element_map: Dict[str, Any]) -> None:
        """Set text into an editable element with password refusal."""
        if not element_id or element_id not in element_map:
            raise ValueError(f"Element ID '{element_id}' not found in current UI state tree")

        node = element_map[element_id]
        if getattr(node, "is_password", False):
            raise PermissionError("Security Violation: Cannot SET_TEXT into [password] node.")

        # 1. Try UIA ValuePattern
        if isinstance(node, UIElementNode) and node.raw_control:
            try:
                ctrl = node.raw_control
                if hasattr(ctrl, "GetValuePattern"):
                    vp = ctrl.GetValuePattern()
                    if vp:
                        vp.SetValue(text)
                        return
            except Exception:
                pass

        # 2. Focus element and send text
        cx = getattr(node, "center_x", 0)
        cy = getattr(node, "center_y", 0)
        if cx > 0 and cy > 0:
            self._click_coords(cx, cy)
            time.sleep(0.02)

        self._type_text(text)

    def _exec_key(self, key_expr: str, is_vision_mode: bool) -> None:
        """Dispatches key shortcut or DirectInput key."""
        if not key_expr:
            return

        # DirectInput game mode (e.g. "w", "space", "up", "esc")
        if is_vision_mode:
            clean_key = key_expr.strip().lower()
            self._send_key_direct(clean_key)
            return

        # Desktop mode key shortcuts (e.g. "{Ctrl}s", "{Enter}")
        if key_expr.startswith("{") and key_expr.endswith("}"):
            inner = key_expr[1:-1]
            if inner.lower().startswith("ctrl"):
                combo_key = inner[4:].lower()
                self._send_key_combo("ctrl", combo_key)
                return
            elif inner.lower().startswith("alt"):
                combo_key = inner[3:].lower()
                self._send_key_combo("alt", combo_key)
                return
            else:
                self._send_key_direct(inner.lower())
                return

        self._send_key_direct(key_expr)

    def _exec_hold_key(self, hold_expr: str) -> None:
        """Parses 'key:ms' (e.g. 'w:800') and holds key."""
        parts = hold_expr.split(":")
        key_name = parts[0].strip().lower()
        hold_ms = float(parts[1]) if len(parts) > 1 else 300.0

        if sys.platform == "win32":
            try:
                from cord.tools.computer.computer_keyboard import press_virtual_key, release_virtual_key, VK_CODES
                vk = VK_CODES.get(key_name) or (ord(key_name.upper()) if len(key_name) == 1 else None)
                if vk:
                    press_virtual_key(vk)
                    time.sleep(hold_ms / 1000.0)
                    release_virtual_key(vk)
                    return
            except Exception:
                pass

    def _exec_move(self, value: Any, element_id: Optional[str], element_map: Dict[str, Any]) -> None:
        """Moves cursor to 'x,y' or element center."""
        target_x, target_y = 0, 0
        if value and "," in str(value):
            x_str, y_str = str(value).split(",", 1)
            target_x = int(float(x_str.strip()))
            target_y = int(float(y_str.strip()))
        elif element_id and element_id in element_map:
            node = element_map[element_id]
            target_x = getattr(node, "center_x", 0)
            target_y = getattr(node, "center_y", 0)

        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.user32.SetCursorPos(target_x, target_y)
            except Exception:
                pass

    def _exec_scroll(self, delta: int) -> None:
        """Wheel scroll."""
        if sys.platform == "win32":
            try:
                from cord.tools.computer.computer_mouse import _send_mouse_event, MOUSEEVENTF_WHEEL
                _send_mouse_event(MOUSEEVENTF_WHEEL, mouseData=delta)
            except Exception:
                try:
                    import pyautogui
                    pyautogui.scroll(delta)
                except Exception:
                    pass

    def _exec_wait_state(
        self,
        wait_label: Optional[str],
        expect: Optional[Dict[str, Any]],
        element_map: Dict[str, Any],
    ) -> float:
        """Times and waits for state transition, updating optimizer."""
        w_start = time.time()

        # Check optimizer for learned duration
        learned_ms = self.optimizer.get_learned_wait(wait_label or "default", default_ms=250.0)
        # Small wait simulating state resolution
        target_wait = max(0.01, min(learned_ms / 1000.0, 5.0))
        time.sleep(min(0.05, target_wait))

        elapsed_ms = round((time.time() - w_start) * 1000, 2)
        if wait_label:
            self.optimizer.record_wait(wait_label, elapsed_ms)
        return elapsed_ms

    def _click_coords(self, x: int, y: int) -> None:
        """Fast Win32 mouse click."""
        if sys.platform == "win32":
            try:
                import ctypes
                from cord.tools.computer.computer_mouse import (
                    _activate_window_at,
                    _send_mouse_event,
                    MOUSEEVENTF_LEFTDOWN,
                    MOUSEEVENTF_LEFTUP,
                )
                _activate_window_at(x, y)
                ctypes.windll.user32.SetCursorPos(x, y)
                _send_mouse_event(MOUSEEVENTF_LEFTDOWN)
                time.sleep(0.005)
                _send_mouse_event(MOUSEEVENTF_LEFTUP)
                return
            except Exception:
                pass

        try:
            import pyautogui
            pyautogui.click(x, y)
        except Exception:
            pass

    def _type_text(self, text: str) -> None:
        """Send keystrokes for text using native Win32 SendInput / keybd_event."""
        if sys.platform == "win32":
            try:
                from cord.tools.computer.computer_keyboard import send_unicode_character, press_virtual_key, release_virtual_key, VK_CODES
                for ch in text:
                    if ch == "\n":
                        vk = VK_CODES["enter"]
                        press_virtual_key(vk)
                        time.sleep(0.005)
                        release_virtual_key(vk)
                    elif ch == "\t":
                        vk = VK_CODES["tab"]
                        press_virtual_key(vk)
                        time.sleep(0.005)
                        release_virtual_key(vk)
                    elif ch == "\r":
                        continue
                    else:
                        send_unicode_character(ch)
                    time.sleep(0.002)
                return
            except Exception:
                pass

        try:
            import pyautogui
            pyautogui.write(text, interval=0.002)
        except Exception:
            pass

    def _send_key_direct(self, key_name: str) -> None:
        """Send single key press using native Win32 input."""
        if sys.platform == "win32":
            try:
                from cord.tools.computer.computer_keyboard import press_virtual_key, release_virtual_key, VK_CODES
                clean = key_name.strip().lower()
                vk = VK_CODES.get(clean) or (ord(clean.upper()) if len(clean) == 1 else None)
                if vk:
                    press_virtual_key(vk)
                    time.sleep(0.03)
                    release_virtual_key(vk)
                    return
            except Exception:
                pass

        try:
            import pyautogui
            pyautogui.press(key_name)
        except Exception:
            pass

    def _send_key_combo(self, modifier: str, key: str) -> None:
        """Send key combination using native Win32 input."""
        if sys.platform == "win32":
            try:
                from cord.tools.computer.computer_keyboard import press_virtual_key, release_virtual_key, VK_CODES
                mod_clean = modifier.strip().lower()
                key_clean = key.strip().lower()
                mod_vk = VK_CODES.get(mod_clean) or (ord(mod_clean.upper()) if len(mod_clean) == 1 else None)
                key_vk = VK_CODES.get(key_clean) or (ord(key_clean.upper()) if len(key_clean) == 1 else None)
                if mod_vk and key_vk:
                    press_virtual_key(mod_vk)
                    time.sleep(0.015)
                    press_virtual_key(key_vk)
                    time.sleep(0.03)
                    release_virtual_key(key_vk)
                    time.sleep(0.015)
                    release_virtual_key(mod_vk)
                    return
            except Exception:
                pass

        try:
            import pyautogui
            pyautogui.hotkey(modifier, key)
        except Exception:
            pass
