"""CORD Core - Autonomous Agent Runtime Loop (Observe-Plan-Tool-Verify-Reflect)"""
from __future__ import annotations
import json
import time
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional

from cord.core.config import CordConfig
from cord.models.ai_manager import ai_manager
from cord.models.model_router import model_router, ModelRole
from cord.tools.registry import ToolRegistry
from cord.tasks.task_manager import task_manager, TaskManager
from cord.tasks.task_state import TaskState
from cord.core.verification_engine import verification_engine, VerificationResult
from cord.memory.output_cache import output_cache
from cord.vision.safety import computer_safety
from cord.ui.console import ui

SYSTEM_PROMPT_AUTONOMOUS = """You are CORD, an elite Principal Autonomous AI Software Engineer and Systems Agent.
Your operational mandate is AGENT-FIRST:
1. NEVER stop after one step. Pursue the user's objective to complete, verified resolution.
2. When implementing features or fixing bugs: inspect the codebase, write real production code, test it, verify syntax and edge cases, and ensure no regressions.
3. If an error or test failure occurs, DO NOT give up. Diagnose the root cause, apply a correction, and re-verify.
4. Always prioritize safety: avoid catastrophic operations outside the workspace.
5. Use the provided tools directly to observe results and complete tasks.
"""

class AgentRuntime:
    """Orchestrates the continuous closed-loop autonomous execution cycle."""

    def __init__(
        self,
        config: CordConfig,
        tool_registry: ToolRegistry,
        task_mgr: Optional[TaskManager] = None
    ):
        self.config = config
        self.tool_registry = tool_registry
        self.task_manager = task_mgr or task_manager
        self.history: List[Dict[str, Any]] = []

    async def run_goal(self, goal: str, max_iterations: int = 25) -> str:
        """Executes the full autonomous closed loop until the goal is satisfied or limits reached."""
        ui.console.print(f"\n[bold green]⚡ CORD Autonomous Runtime Activated[/bold green]")
        ui.console.print(f"[bold bright_white]Goal:[/bold bright_white] {goal}\n")

        self.task_manager.set_goal(goal)
        initial_task = self.task_manager.add_task(title=goal)
        self.task_manager.update_task_state(initial_task.id, TaskState.RUNNING)

        self.history = [
            {"role": "system", "content": SYSTEM_PROMPT_AUTONOMOUS},
            {"role": "user", "content": f"User Objective: {goal}\nWorkspace: {self.config.workspace_dir}"}
        ]

        iteration = 0
        final_answer = ""

        while iteration < max_iterations:
            iteration += 1

            # Check emergency stop / kill switch
            if computer_safety.is_stopped():
                ui.print_error("Execution halted: Kill Switch triggered!")
                self.task_manager.update_task_state(initial_task.id, TaskState.CANCELLED, error="Kill Switch")
                return "Operation aborted by user emergency stop."

            # Determine appropriate model
            active_model = model_router.resolve_for_role(
                ModelRole.CODING,
                preferred_model=self.config.model
            )

            # Fetch schemas
            tool_schemas = self.tool_registry.get_schemas()

            ui.print_info(f"[dim]Step {iteration}/{max_iterations} (Model: {active_model})[/dim]")

            # Call AI
            try:
                response = await ai_manager.chat_complete(
                    messages=self.history,
                    model=active_model,
                    tools=tool_schemas,
                    temperature=self.config.temperature,
                )
            except Exception as e:
                ui.print_error(f"LLM generation failed: {e}")
                return f"Execution interrupted due to model error: {e}"

            content = response.get("content") or ""
            tool_calls = response.get("tool_calls") or []

            # Fallback Tool Recovery for models that output XML tool tags
            if not tool_calls and content:
                from cord.core.tool_parser import parse_fallback_tool_calls, strip_tool_xml_from_text
                recovered = parse_fallback_tool_calls(content, self.tool_registry.tools)
                if recovered:
                    tool_calls = recovered
                    content = strip_tool_xml_from_text(content, recovered)

            # Append assistant message to history
            assistant_msg: Dict[str, Any] = {"role": "assistant"}
            if content:
                assistant_msg["content"] = content
            if tool_calls:
                assistant_msg["tool_calls"] = tool_calls
            self.history.append(assistant_msg)

            if content and not tool_calls:
                # LLM provided thoughts or final message
                ui.console.print(f"[bright_white]{content}[/bright_white]")
                final_answer = content

            # If no tool calls were made and LLM answered, check if goal is complete
            if not tool_calls:
                self.task_manager.update_task_state(initial_task.id, TaskState.COMPLETED)
                ui.console.print(f"\n[bold green]✓ Goal completed in {iteration} steps.[/bold green]")
                return final_answer or "Goal completed successfully."

            # Process tool calls
            modified_files: List[str] = []
            for tc in tool_calls:
                tc_id = tc.get("id") or f"call_{uuid.uuid4().hex[:12]}"
                fn = tc.get("function", {})
                name = fn.get("name")
                raw_args = fn.get("arguments", "{}")

                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except Exception:
                    args = {}

                # Track file modifications for verification
                if name in ["write_file", "edit_file"] and "path" in args:
                    modified_files.append(args["path"])

                # Execute tool
                tool_res = await self.tool_registry.execute(name, args)

                raw_output = tool_res.output or tool_res.error or ("Success" if tool_res.success else "Failed")
                summary_output, truncated, log_path = output_cache.cache_and_truncate(raw_output)

                # Record tool response in conversation
                self.history.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "name": name,
                    "content": summary_output
                })

            # Automated Verification Step
            if modified_files:
                self.task_manager.update_task_state(initial_task.id, TaskState.VERIFYING)
                ui.print_info(f"[bold cyan]🔍 Verifying {len(modified_files)} modified file(s)...[/bold cyan]")
                v_res: VerificationResult = verification_engine.verify_change(modified_files, run_tests=True)

                if not v_res.passed:
                    ui.print_warning("Verification detected issues. Instructing agent to reflect and fix...")
                    issues_str = "\n".join(f"- {iss}" for iss in v_res.issues)
                    feedback = (
                        f"[AUTOMATED VERIFICATION ALERT]\n"
                        f"Issues found after your changes:\n{issues_str}\n"
                    )
                    if v_res.test_output:
                        feedback += f"\nTest Output:\n{v_res.test_output[-1000:]}\n"
                    feedback += "Diagnose the error, fix the modified code, and verify again."

                    self.history.append({
                        "role": "user",
                        "content": feedback
                    })
                    self.task_manager.update_task_state(initial_task.id, TaskState.RUNNING)
                else:
                    ui.print_info("[bold green]✓ Code syntax and test checks passed.[/bold green]")
                    self.task_manager.update_task_state(initial_task.id, TaskState.RUNNING)

        ui.print_warning(f"Maximum autonomous iterations ({max_iterations}) reached.")
        return final_answer or "Autonomous loop reached iteration limit."
