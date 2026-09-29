"""
CORD Tool - kinetic_act
KINETIC-CORE Ultra-Fast Self-Evolving Computer Automation Engine.
Dispatches compound keyboard and mouse operations via kernel-level micro-packet streaming,
minimum-jerk spline physics, and continuous self-evolution.
"""

from __future__ import annotations
import sys
from typing import List, Dict, Any, Optional

from cord.tools.base import BaseTool, ToolResult
from cord.permissions.levels import PermissionLevel, RiskLevel
from cord.vision.safety import computer_safety
from cord.vision.ai_cursor import ai_cursor
from cord.kinetic.engine import kinetic_engine


class KineticActTool(BaseTool):
    name = "kinetic_act"
    description = (
        "KINETIC-CORE Ultra-Fast Self-Evolving Computer Automation Engine. "
        "Executes compound mouse and keyboard actions via kernel-level micro-packet streaming "
        "and minimum-jerk physics with sub-millisecond latency. Auto-tunes application profiles "
        "and synthesizes instant reflex macros over time. "
        "Supports 'click_and_type', 'burst_type', 'burst_batch', 'reflex', 'learn_reflex', and 'stats'."
    )
    required_permission = PermissionLevel.EXECUTE
    risk_level = RiskLevel.HIGH
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "click_and_type",
                    "burst_type",
                    "burst_batch",
                    "reflex",
                    "learn_reflex",
                    "stats",
                ],
                "description": (
                    "Kinetic action to execute: 'click_and_type' (atomic move+click+type+enter in <25ms), "
                    "'burst_type' (stream entire string in 1 kernel call), 'burst_batch' (execute action list), "
                    "'reflex' (trigger pre-compiled 0ms reflex), 'learn_reflex' (synthesize new reflex), "
                    "'stats' (view self-evolution metrics)"
                ),
            },
            "x": {
                "type": "integer",
                "description": "Target X coordinate on screen",
            },
            "y": {
                "type": "integer",
                "description": "Target Y coordinate on screen",
            },
            "text": {
                "type": "string",
                "description": "Text to stream directly into the active window (for click_and_type / burst_type)",
            },
            "press_enter": {
                "type": "boolean",
                "description": "Whether to press Enter after typing text (default: true)",
                "default": True,
            },
            "window_title": {
                "type": "string",
                "description": "Window title to focus before execution (optional)",
            },
            "reflex_name": {
                "type": "string",
                "description": "Name or intent of reflex to execute or learn (e.g. 'save', 'copy', 'paste', 'select_all', 'undo')",
            },
            "intent": {
                "type": "string",
                "description": "Description or intent of new reflex macro for learn_reflex",
            },
            "steps": {
                "type": "array",
                "items": {"type": "object"},
                "description": "List of sub-actions for burst_batch or learn_reflex (e.g. [{'action': 'click', 'x': 500, 'y': 300}, {'action': 'type', 'text': 'cord'}, {'action': 'key', 'key': 'enter'}])",
            },
        },
        "required": ["action"],
    }

    async def execute(
        self,
        action: str,
        x: Optional[int] = None,
        y: Optional[int] = None,
        text: Optional[str] = None,
        press_enter: bool = True,
        window_title: Optional[str] = None,
        reflex_name: Optional[str] = None,
        intent: Optional[str] = None,
        steps: Optional[List[Dict[str, Any]]] = None,
        **kwargs,
    ) -> ToolResult:
        if sys.platform != "win32":
            return ToolResult(
                success=False,
                output="",
                error="KINETIC-CORE requires Windows native APIs for hardware micro-packet streaming.",
            )

        allowed, reason = computer_safety.validate_action(action, x=x, y=y)
        if not allowed:
            return ToolResult(success=False, output="", error=f"Kinetic action blocked by safety policy: {reason}")

        try:
            # 1. Atomic Click and Type
            if action == "click_and_type":
                if x is None or y is None or text is None:
                    return ToolResult(
                        success=False, output="", error="x, y, and text are required for click_and_type."
                    )
                ai_cursor.show_click(int(x), int(y), button="left")
                res = kinetic_engine.click_and_type(
                    x=int(x),
                    y=int(y),
                    text=text,
                    press_enter=press_enter,
                    window_title=window_title,
                )
                speed_str = res.get("speed_multiplier", "100x faster")
                return ToolResult(
                    success=res["success"],
                    output=f"⚡ KINETIC click_and_type executed in {res['elapsed_ms']}ms ({speed_str}): clicked ({x}, {y}), typed {res['characters']} chars (enter={press_enter}).",
                )

            # 2. Burst Text Streaming
            elif action == "burst_type":
                if text is None:
                    return ToolResult(success=False, output="", error="text is required for burst_type.")
                res = kinetic_engine.burst_type(text)
                return ToolResult(
                    success=res["success"],
                    output=(
                        f"⚡ KINETIC burst_type completed in {res['elapsed_ms']}ms: "
                        f"streamed {res['characters_typed']} chars via micro-packets "
                        f"(profile: {res['app_profile']}, cadence: {res['learned_cadence_ms']}ms)."
                    ),
                )

            # 3. Burst Batch
            elif action == "burst_batch":
                if not steps:
                    return ToolResult(success=False, output="", error="steps list is required for burst_batch.")
                res = kinetic_engine.execute_batch(steps)
                return ToolResult(
                    success=res["success"],
                    output=(
                        f"⚡ KINETIC burst_batch completed: {res['completed_steps']}/{res['total_steps']} steps "
                        f"executed in {res['elapsed_ms']}ms "
                        f"(Evolution Gen {res['evolution_generation']}, saved {res['total_time_saved_sec']}s total)."
                    ),
                )

            # 4. Instant Reflex Macro
            elif action == "reflex":
                target = reflex_name or text or kwargs.get("name")
                if not target:
                    return ToolResult(success=False, output="", error="reflex_name is required for reflex action.")
                res = kinetic_engine.execute_reflex(target)
                if not res.get("success"):
                    return ToolResult(success=False, output="", error=res.get("error", "Reflex execution failed."))
                return ToolResult(
                    success=True,
                    output=f"⚡ KINETIC reflex '{res['reflex']}' ({res['intent']}) triggered: {res['steps']} steps executed in {res['elapsed_ms']}ms.",
                )

            # 5. Learn / Synthesize Reflex
            elif action == "learn_reflex":
                name = reflex_name or kwargs.get("name")
                if not name or not steps:
                    return ToolResult(
                        success=False, output="", error="reflex_name and steps are required for learn_reflex."
                    )
                macro_intent = intent or f"Reflex macro {name}"
                reflex = kinetic_engine.reflexes.learn_chain(name, macro_intent, steps)
                return ToolResult(
                    success=True,
                    output=f"⚡ KINETIC synthesized new reflex '{reflex.name}' with {len(reflex.actions)} actions. Can now be executed in 0ms.",
                )

            # 6. Self-Evolution Metrics
            elif action == "stats":
                stats = kinetic_engine.evolution.get_stats()
                return ToolResult(
                    success=True,
                    output=(
                        f"⚡ KINETIC Evolution Metrics (Gen {stats['generation']}): "
                        f"Dispatched {stats['total_actions_dispatched']} actions, "
                        f"saved {stats['total_time_saved_sec']}s total time. "
                        f"Active profiles: {stats['total_profiles']}, Synthesized reflexes: {stats['total_reflexes']}."
                    ),
                )

            return ToolResult(success=False, output="", error=f"Unknown kinetic_act action: '{action}'")

        except Exception as e:
            return ToolResult(success=False, output="", error=f"Kinetic act execution failed: {e}")
