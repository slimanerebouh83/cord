"""
NITEE v3 - Planner Core Orchestrator
Coordinates Structural Tree capture, Vision Matcher, Wait State Optimizer,
Reflex Engine, Low-Latency Local Executor, and Reusable Skill Compiler.
"""

from __future__ import annotations
import re
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

from cord.nitee.structural_tree import StructuralTree, UIElementNode
from cord.nitee.vision_matcher import VisionMatcher, VisionObject
from cord.nitee.optimizer import WaitOptimizer
from cord.nitee.reflex_engine import ReflexEngine
from cord.nitee.executor import NiteeExecutor
from cord.nitee.skill_compiler import SkillCompiler


class NiteeCore:
    """Core orchestrator for NITEE v3 automation cycles."""

    def __init__(
        self,
        optimizer_path: Optional[Path] = None,
        templates_dir: Optional[Path] = None,
        skills_dir: Optional[Path] = None,
    ):
        self.structural_tree = StructuralTree()
        self.vision_matcher = VisionMatcher(templates_dir=templates_dir)
        self.optimizer = WaitOptimizer(storage_path=optimizer_path)
        self.executor = NiteeExecutor(optimizer=self.optimizer)
        self.reflex_engine = ReflexEngine(vision_matcher=self.vision_matcher)
        self.skill_compiler = SkillCompiler(storage_dir=skills_dir)
        self._current_element_map: Dict[str, Any] = {}
        self._current_mode: str = "desktop"

    @property
    def element_map(self) -> Dict[str, Any]:
        return self._current_element_map

    def capture_state(
        self,
        mode: str = "desktop",
        window_query: Optional[str] = None,
        frame_image: Optional[Any] = None,
    ) -> Tuple[str, Dict[str, Any], str]:
        """Capture current UI state.
        
        Args:
            mode: 'desktop', 'web', or 'game'
            window_query: Optional window title substring
            frame_image: Optional frame image for vision mode
            
        Returns:
            (ui_tree_text, element_map, active_window_context)
        """
        self._current_mode = mode.lower()
        if self._current_mode == "game":
            tree_text, vision_map = self.vision_matcher.detect_objects(frame_image=frame_image)
            self._current_element_map = dict(vision_map)
            active_window = "GAME_VISION"
            return tree_text, self._current_element_map, active_window
        else:
            tree_text, struct_map = self.structural_tree.capture(window_title_query=window_query)
            self._current_element_map = dict(struct_map)
            active_window = self.structural_tree.active_window_title or "Desktop"
            return tree_text, self._current_element_map, active_window

    def build_cycle_input(
        self,
        goal: str,
        mode: str = "desktop",
        window_query: Optional[str] = None,
        frame_image: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Generate structured inputs for the NITEE planner model."""
        tree_text, el_map, active_window = self.capture_state(
            mode=mode, window_query=window_query, frame_image=frame_image
        )
        optimizer_stats = self.optimizer.get_stats()

        formatted_input = {
            "GOAL": goal,
            "ACTIVE_WINDOW": active_window,
            "OPTIMIZER": optimizer_stats,
            "ui_tree": tree_text,
            "element_count": len(el_map),
        }
        return formatted_input

    def parse_response(self, response_str: str) -> Dict[str, Any]:
        """Parse and validate the strict JSON response from the NITEE planner model."""
        clean = response_str.strip()

        # Remove markdown code fences if wrapped
        if clean.startswith("```"):
            lines = clean.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            clean = "\n".join(lines).strip()

        try:
            data = json.loads(clean)
        except json.JSONDecodeError as e:
            # Fallback regex extraction for JSON block
            match = re.search(r"(\{.*\})", clean, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                except Exception:
                    raise ValueError(f"NITEE protocol error: Invalid JSON syntax ({e}). Response was: {clean[:200]}")
            else:
                raise ValueError(f"NITEE protocol error: Invalid JSON syntax ({e}). Response was: {clean[:200]}")

        # Validate mandatory fields
        required_fields = ["analysis", "plan", "reflex_rules", "reflex_seconds", "done", "summary"]
        for field in required_fields:
            if field not in data:
                raise ValueError(f"NITEE protocol error: Missing mandatory field '{field}' in response JSON.")

        if not isinstance(data["plan"], list):
            raise ValueError("NITEE protocol error: 'plan' must be a list of action objects.")

        return data

    def execute_cycle(
        self,
        parsed_plan: Dict[str, Any],
        goal: str = "",
        allow_high_risk: bool = False,
    ) -> Dict[str, Any]:
        """Executes plan batch and reflex rules, updating optimizer and compiling skills."""
        is_vision = (self._current_mode == "game")
        plan_steps = parsed_plan.get("plan", [])
        reflex_rules = parsed_plan.get("reflex_rules", [])
        reflex_seconds = float(parsed_plan.get("reflex_seconds", 0))
        is_done = bool(parsed_plan.get("done", False))
        summary = str(parsed_plan.get("summary", ""))

        # 1. Execute Big Certain Batch
        batch_result = self.executor.execute_batch(
            plan=plan_steps,
            element_map=self._current_element_map,
            is_vision_mode=is_vision,
            allow_high_risk=allow_high_risk,
        )

        # 2. Execute Reflex Rules burst if specified
        reflex_result = None
        if reflex_rules and reflex_seconds > 0:
            reflex_result = self.reflex_engine.run_burst(
                rules=reflex_rules,
                reflex_seconds=reflex_seconds,
            )

        # 3. If finished cleanly and marked DONE, compile into deterministic skill
        compiled_skill = None
        if is_done and batch_result.get("success", False) and goal:
            try:
                compiled_skill = self.skill_compiler.compile(
                    goal=goal,
                    plan=plan_steps,
                    summary=summary,
                    metadata={"total_ms": batch_result.get("total_ms", 0)},
                )
            except Exception:
                pass

        return {
            "success": batch_result.get("success", False),
            "batch_result": batch_result,
            "reflex_result": reflex_result,
            "compiled_skill": compiled_skill,
            "done": is_done,
            "summary": summary,
            "analysis": parsed_plan.get("analysis", ""),
        }
