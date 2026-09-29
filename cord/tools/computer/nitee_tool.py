"""
CORD Tool - nitee_act
Native Tool Wrapper for the NITEE v3 Planner Core Engine.
Ultra-fast structural UI automation, certain batch execution, reflex engine bursts,
and self-optimizing wait states.
"""

from __future__ import annotations
import json
from typing import Dict, Any, List, Optional

from cord.tools.base import BaseTool, ToolResult
from cord.permissions.levels import PermissionLevel, RiskLevel
from cord.nitee import NiteeCore


class NiteePlannerTool(BaseTool):
    name = "nitee_act"
    description = (
        "NITEE v3 Planner Core: Ultra-fast structural UI/accessibility tree automation. "
        "Supports 'inspect' (captures current <ui_tree> and learned wait durations), "
        "'execute_batch' (runs 3-10 concrete plan steps in 1-10 ms per action), "
        "'reflex_burst' (runs 20-60 Hz frame-rate reactions without LLM latency), "
        "'replay_skill' (zero-LLM deterministic skill replay), and 'list_skills'."
    )
    required_permission = PermissionLevel.EXECUTE
    risk_level = RiskLevel.HIGH
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "inspect",
                    "execute_batch",
                    "reflex_burst",
                    "replay_skill",
                    "list_skills",
                    "get_optimizer_stats",
                ],
                "description": "Action to perform with NITEE v3."
            },
            "mode": {
                "type": "string",
                "enum": ["desktop", "web", "game"],
                "description": "Surface mode: 'desktop'/'web' (structural accessibility tree) or 'game' (vision template matching).",
                "default": "desktop"
            },
            "window_query": {
                "type": "string",
                "description": "Optional title query to focus and inspect a specific application window."
            },
            "goal": {
                "type": "string",
                "description": "User goal description (used for context and automatic skill compilation)."
            },
            "plan": {
                "type": "array",
                "items": {"type": "object"},
                "description": "Batch of 3-10 concrete plan steps: [{'step': 1, 'action': 'CLICK', 'element_id': 'n_12', ...}]"
            },
            "reflex_rules": {
                "type": "array",
                "items": {"type": "object"},
                "description": "List of 20-60 Hz reflex rules: [{'if': {'see': 'enemy'}, 'then': {'action': 'CLICK_ON'}, 'cooldown_ms': 250}]"
            },
            "reflex_seconds": {
                "type": "number",
                "description": "Duration in seconds (1 to 10) for reflex engine burst.",
                "default": 0
            },
            "skill_name": {
                "type": "string",
                "description": "Name of compiled skill to replay."
            },
            "allow_high_risk": {
                "type": "boolean",
                "description": "Explicit approval for high-risk irreversible actions (submit, send, pay, delete).",
                "default": False
            }
        },
        "required": ["action"]
    }

    def __init__(self, core: Optional[NiteeCore] = None):
        super().__init__()
        self._core = core or NiteeCore()

    async def execute(
        self,
        action: str,
        mode: str = "desktop",
        window_query: Optional[str] = None,
        goal: Optional[str] = None,
        plan: Optional[List[Dict[str, Any]]] = None,
        reflex_rules: Optional[List[Dict[str, Any]]] = None,
        reflex_seconds: float = 0.0,
        skill_name: Optional[str] = None,
        allow_high_risk: bool = False,
        **kwargs: Any,
    ) -> ToolResult:
        action_clean = (action or "").strip().lower()

        try:
            if action_clean == "inspect":
                inputs = self._core.build_cycle_input(
                    goal=goal or "Inspect UI state",
                    mode=mode,
                    window_query=window_query,
                )
                return ToolResult(
                    success=True,
                    output=(
                        f"Captured {inputs['element_count']} structural elements for window '{inputs['ACTIVE_WINDOW']}':\n"
                        f"<ui_tree>\n{inputs['ui_tree']}\n</ui_tree>\n"
                        f"Learned Wait Durations: {json.dumps(inputs['OPTIMIZER'])}"
                    ),
                    metadata=inputs,
                )

            elif action_clean == "execute_batch":
                if not plan:
                    return ToolResult(success=False, output="", error="execute_batch requires a non-empty 'plan' array.")

                # If element map is currently empty, perform quick capture first
                if not self._core.element_map:
                    self._core.capture_state(mode=mode, window_query=window_query)

                parsed_plan = {
                    "analysis": "Batch dispatched via nitee_act",
                    "plan": plan,
                    "reflex_rules": reflex_rules or [],
                    "reflex_seconds": reflex_seconds,
                    "done": any((s.get("action") or "").upper() == "DONE" for s in plan),
                    "summary": f"Executed batch of {len(plan)} steps",
                }

                cycle_result = self._core.execute_cycle(
                    parsed_plan=parsed_plan,
                    goal=goal or "",
                    allow_high_risk=allow_high_risk,
                )
                batch_res = cycle_result.get("batch_result", {})
                success = cycle_result.get("success", False)

                summary_lines = [
                    f"NITEE Batch Execution: {'SUCCESS' if success else 'PARTIAL/FAILED'}",
                    f"Completed: {batch_res.get('completed_steps', 0)}/{batch_res.get('total_steps', len(plan))} steps in {batch_res.get('total_ms', 0)} ms",
                ]
                if cycle_result.get("reflex_result"):
                    ref = cycle_result["reflex_result"]
                    summary_lines.append(f"Reflex Burst: {ref.get('total_firings', 0)} triggers across {ref.get('duration_sec', 0)}s")
                if cycle_result.get("compiled_skill"):
                    summary_lines.append(f"Compiled Deterministic Skill: {cycle_result['compiled_skill'].get('name')}")
                if batch_res.get("errors"):
                    summary_lines.append(f"Errors: {'; '.join(batch_res['errors'])}")

                return ToolResult(
                    success=success,
                    output="\n".join(summary_lines),
                    metadata=cycle_result,
                )

            elif action_clean == "reflex_burst":
                if not reflex_rules:
                    return ToolResult(success=False, output="", error="reflex_burst requires a non-empty 'reflex_rules' array.")
                res = self._core.reflex_engine.run_burst(
                    rules=reflex_rules,
                    reflex_seconds=reflex_seconds or 2.0,
                )
                return ToolResult(
                    success=True,
                    output=f"Reflex burst completed in {res.get('duration_sec')}s: {res.get('total_firings')} triggers executed.",
                    metadata=res,
                )

            elif action_clean == "list_skills":
                skills = self._core.skill_compiler.list_skills()
                return ToolResult(
                    success=True,
                    output=f"Found {len(skills)} compiled deterministic skills.",
                    metadata={"skills": skills},
                )

            elif action_clean == "replay_skill":
                if not skill_name:
                    return ToolResult(success=False, output="", error="replay_skill requires 'skill_name'.")
                skill_data = self._core.skill_compiler.load_skill(skill_name)
                if not skill_data:
                    return ToolResult(success=False, output="", error=f"Skill '{skill_name}' not found.")

                steps = skill_data.get("steps", [])
                if not self._core.element_map:
                    self._core.capture_state(mode=mode, window_query=window_query)

                batch_res = self._core.executor.execute_batch(
                    plan=steps,
                    element_map=self._core.element_map,
                    is_vision_mode=(mode == "game"),
                    allow_high_risk=allow_high_risk,
                )
                return ToolResult(
                    success=batch_res.get("success", False),
                    output=f"Replayed skill '{skill_name}': {batch_res.get('completed_steps')}/{len(steps)} steps in {batch_res.get('total_ms')} ms.",
                    metadata=batch_res,
                )

            elif action_clean == "get_optimizer_stats":
                stats = self._core.optimizer.get_stats()
                return ToolResult(
                    success=True,
                    output=f"Learned wait stats: {json.dumps(stats, indent=2)}",
                    metadata=stats,
                )

            else:
                return ToolResult(success=False, output="", error=f"Unknown action '{action}'.")

        except Exception as exc:
            return ToolResult(success=False, output="", error=f"NITEE tool error: {str(exc)}")

