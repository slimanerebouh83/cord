"""
NITEE v3 - Reflex Engine Module
High-frequency local reactive loop (20-60 Hz) evaluating reflex_rules
for sub-second reactions (aiming, dodging, jumping, clicking) without LLM latency.
"""

from __future__ import annotations
import time
import math
import sys
from typing import List, Dict, Any, Optional, Callable
from cord.nitee.vision_matcher import VisionMatcher, VisionObject


class ReflexEngine:
    """Runs a frame-rate reaction loop (20-60 Hz) evaluating reactive rules."""

    def __init__(
        self,
        vision_matcher: Optional[VisionMatcher] = None,
        action_executor: Optional[Callable[[str, Any], Any]] = None,
        frequency_hz: int = 30,
    ):
        self.vision_matcher = vision_matcher or VisionMatcher()
        self.action_executor = action_executor
        self.frequency_hz = max(10, min(60, frequency_hz))
        self._interval = 1.0 / self.frequency_hz
        self._stop_requested = False

    def stop(self) -> None:
        """Signal the reflex loop to terminate early."""
        self._stop_requested = True

    def run_burst(
        self,
        rules: List[Dict[str, Any]],
        reflex_seconds: float,
        frame_provider: Optional[Callable[[], Any]] = None,
    ) -> Dict[str, Any]:
        """Execute reflex loop for reflex_seconds duration.
        
        Args:
            rules: List of reflex rules
            reflex_seconds: Duration in seconds (1 to 10s)
            frame_provider: Optional callable yielding screen images/simulated state
            
        Returns:
            Execution summary dict
        """
        if not rules or reflex_seconds <= 0:
            return {"total_firings": 0, "actions_taken": [], "duration_sec": 0.0}

        # Clamp reflex duration to 1-10s per NITEE specification
        duration = max(0.1, min(10.0, float(reflex_seconds)))
        start_time = time.time()
        end_time = start_time + duration
        self._stop_requested = False

        cooldowns: Dict[int, float] = {i: 0.0 for i in range(len(rules))}
        actions_log: List[str] = []
        firings_count = 0

        # Screen dimensions / center reference
        screen_cx, screen_cy = 960, 540
        if sys.platform == "win32":
            try:
                import ctypes
                user32 = ctypes.windll.user32
                screen_cx = user32.GetSystemMetrics(0) // 2
                screen_cy = user32.GetSystemMetrics(1) // 2
            except Exception:
                pass

        while time.time() < end_time and not self._stop_requested:
            loop_start = time.time()

            # 1. Grab visual objects
            frame = frame_provider() if frame_provider else None
            _, nodes_map = self.vision_matcher.detect_objects(frame_image=frame)

            now = time.time()

            # 2. Evaluate rules in priority order
            for idx, rule in enumerate(rules):
                cond = rule.get("if", {})
                then = rule.get("then", {})
                cooldown_ms = float(rule.get("cooldown_ms", 200))
                cooldown_sec = cooldown_ms / 1000.0

                # Check cooldown
                if now - cooldowns[idx] < cooldown_sec:
                    continue

                target_see = cond.get("see", "").strip().lower()
                min_conf = float(cond.get("min_conf", 0.70))
                max_dist = cond.get("max_dist_from_center")

                # Find candidate objects matching condition
                matching_objects: List[Tuple[float, VisionObject]] = []
                for v_obj in nodes_map.values():
                    if v_obj.label.lower() == target_see and v_obj.confidence >= min_conf:
                        dist = math.hypot(v_obj.center_x - screen_cx, v_obj.center_y - screen_cy)
                        if max_dist is None or dist <= float(max_dist):
                            matching_objects.append((dist, v_obj))

                # If condition matched
                if matching_objects:
                    # Pick nearest to screen center per NITEE spec
                    matching_objects.sort(key=lambda x: x[0])
                    nearest_dist, target_obj = matching_objects[0]

                    # Trigger reactive action
                    action_type = then.get("action", "").upper()
                    val = then.get("value")

                    self._execute_reflex_action(action_type, val, target_obj)

                    cooldowns[idx] = now
                    firings_count += 1
                    log_entry = f"[{idx}] {action_type} on {target_obj.label}@{target_obj.center_x},{target_obj.center_y}"
                    actions_log.append(log_entry)
                    break  # Highest priority matching rule triggers this frame

            elapsed_frame = time.time() - loop_start
            sleep_time = self._interval - elapsed_frame
            if sleep_time > 0:
                time.sleep(sleep_time)

        real_duration = round(time.time() - start_time, 3)
        return {
            "total_firings": firings_count,
            "actions_taken": actions_log,
            "duration_sec": real_duration,
        }

    def _execute_reflex_action(self, action_type: str, value: Any, target_obj: VisionObject) -> None:
        """Dispatches sub-millisecond reflex action."""
        if self.action_executor:
            try:
                self.action_executor(action_type, {"value": value, "target": target_obj})
                return
            except Exception:
                pass

        # Native DirectInput / Win32 dispatch
        if sys.platform == "win32":
            try:
                import ctypes
                from cord.tools.computer.computer_mouse import _send_mouse_event, MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP

                user32 = ctypes.windll.user32
                if action_type == "CLICK_ON":
                    user32.SetCursorPos(target_obj.center_x, target_obj.center_y)
                    _send_mouse_event(MOUSEEVENTF_LEFTDOWN)
                    time.sleep(0.01)
                    _send_mouse_event(MOUSEEVENTF_LEFTUP)

                elif action_type == "MOVE":
                    user32.SetCursorPos(target_obj.center_x, target_obj.center_y)

                elif action_type == "KEY":
                    self._dispatch_key(str(value or "space"))

                elif action_type == "HOLD_KEY":
                    val_str = str(value or "w:300")
                    if ":" in val_str:
                        key_name, hold_ms_str = val_str.split(":", 1)
                        hold_ms = float(hold_ms_str)
                    else:
                        key_name = val_str
                        hold_ms = 300.0
                    self._hold_key(key_name, hold_ms)
            except Exception:
                pass

    def _dispatch_key(self, key_name: str) -> None:
        """Send DirectInput key press & release."""
        try:
            import pyautogui
            pyautogui.press(key_name)
        except Exception:
            pass

    def _hold_key(self, key_name: str, hold_ms: float) -> None:
        """Hold key down for specified milliseconds then release."""
        try:
            import pyautogui
            pyautogui.keyDown(key_name)
            time.sleep(hold_ms / 1000.0)
            pyautogui.keyUp(key_name)
        except Exception:
            pass
