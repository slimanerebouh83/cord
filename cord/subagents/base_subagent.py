"""
CORD Subagents - Base Subagent Definition and Execution Loop
Universal autonomous subagent with parent config inheritance, model overrides,
streaming thinking, resilient tool calling, and auto-failover.
"""

from __future__ import annotations
import json
import time
import copy
import inspect
import asyncio
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field

from cord.core.config import CordConfig
from cord.core.llm import LLMClient, LLMError
from cord.tools.base import BaseTool, ToolResult
from cord.ui.console import ui
from cord.ui.animations import ThinkingAnimation


@dataclass
class SubagentResult:
    role: str
    task: str
    success: bool
    summary: str
    details: str = ""
    tool_calls_count: int = 0
    model: str = ""
    provider: str = ""


# Aliases mapping common alternative tool names to standard CORD tool names
TOOL_ALIASES: Dict[str, str] = {
    "list_dir": "list_directory",
    "ls": "list_directory",
    "dir": "list_directory",
    "search": "search_files",
    "find_files": "search_files",
    "grep_search": "search_files",
    "grep": "search_files",
    "run_shell": "execute_command",
    "shell": "execute_command",
    "bash": "execute_command",
    "cmd": "execute_command",
    "terminal": "execute_command",
    "system_overview": "get_system_info",
    "sysinfo": "get_system_info",
}


class Subagent:
    """An autonomous sub-agent running an isolated loop with a specialized role and tools."""

    def __init__(
        self,
        name: str,
        role: str,
        system_prompt: str,
        config: CordConfig,
        tools: List[BaseTool],
        max_iterations: int = 15,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        parent_name: Optional[str] = None,
    ):
        self.name = name
        self.role = role
        self.system_prompt = system_prompt
        self.parent_name = parent_name or "main"

        # Clone config to isolate subagent settings, strictly inheriting from spawning entity
        self.config = copy.copy(config)
        if model:
            self.config.model = model
        if provider:
            self.config.provider = provider

        # Register tools with canonical names and alias mappings
        self.tools: Dict[str, BaseTool] = {}
        for t in tools:
            self.tools[t.name] = t
            # Also register alias if applicable
            for alias, canonical in TOOL_ALIASES.items():
                if canonical == t.name and alias not in self.tools:
                    self.tools[alias] = t

        self.max_iterations = max_iterations
        self.llm = LLMClient(self.config)
        self.messages: List[Dict[str, Any]] = []
        self.id = name
        self.status = "idle"
        self.created_at = time.time()
        self.last_active = time.time()
        self.summary = ""
        self.total_tool_calls = 0
        self.tool_history: List[Dict[str, Any]] = []
        self.thinking_history: List[str] = []
        self.current_task: str = ""

    def reset_context(self) -> None:
        """Resets the subagent's conversation history."""
        self.messages.clear()
        self.tool_history.clear()
        self.thinking_history.clear()
        self.current_task = ""
        self.status = "idle"

    async def run(self, task: str) -> SubagentResult:
        """Runs the subagent loop on the assigned task."""
        self.status = "running"
        self.last_active = time.time()
        self.current_task = task

        ui.console.print(
            f"\n[bold magenta]🤖 Spawning Subagent: [{self.role.upper()}] - {self.name}[/bold magenta]\n"
            f"[dim]Provider:[/dim] [bold cyan]{self.config.provider}[/bold cyan] │ "
            f"[dim]Model:[/dim] [bold cyan]{self.config.model}[/bold cyan] [dim](Inherited from {self.parent_name})[/dim]\n"
            f"[dim]Task: {task}[/dim]\n"
        )

        if not self.messages:
            self.messages = [
                {"role": "user", "content": f"Task for {self.role.upper()} ({self.name}):\n{task}"}
            ]
        else:
            self.messages.append({"role": "user", "content": task})

        # Use canonical unique tool schemas for LLM declaration
        unique_tools = {t.name: t for t in self.tools.values()}
        tool_schemas = [t.to_schema() for t in unique_tools.values()]
        iterations = 0
        tool_calls_count = 0
        final_summary = ""
        reconnect_attempts = 0

        while iterations < self.max_iterations:
            iterations += 1
            assistant_text = ""
            thinking_text = ""
            tool_calls_dict: Dict[int, Dict[str, Any]] = {}
            thinking_header_printed = False

            # Thinking spinner
            anim = ThinkingAnimation(model_name=f"{self.name} ({self.config.model})")
            await anim.start()

            try:
                async for chunk in self.llm.stream_chat(
                    messages=self.messages,
                    tools=tool_schemas if tool_schemas else None,
                    system_prompt=self.system_prompt,
                ):
                    if anim._running and (chunk.text or chunk.tool_call_delta or chunk.thinking):
                        await anim.stop()

                    if chunk.thinking:
                        thinking_text += chunk.thinking
                        if self.config.show_thinking and getattr(self.config, "thinking_mode", "stream") == "stream":
                            clean_thinking = chunk.thinking
                            if not thinking_header_printed:
                                if not clean_thinking.strip():
                                    continue
                                ui.console.print(f"\n[dim #a855f7]╭─ 🧠 [{self.name}] Thinking... ──╮[/dim #a855f7]")
                                thinking_header_printed = True
                                clean_thinking = clean_thinking.lstrip("\r\n")
                            ui.console.print(f"[dim #c084fc]{clean_thinking}[/dim #c084fc]", end="")

                    if chunk.text:
                        if thinking_header_printed:
                            ui.console.print("\n[dim #a855f7]╰────────────────────────────────╯[/dim #a855f7]\n")
                            thinking_header_printed = False
                        assistant_text += chunk.text

                    if chunk.tool_call_delta:
                        if thinking_header_printed:
                            ui.console.print("\n[dim #a855f7]╰────────────────────────────────╯[/dim #a855f7]\n")
                            thinking_header_printed = False

                        delta = chunk.tool_call_delta
                        idx = delta.index
                        if idx not in tool_calls_dict:
                            tool_calls_dict[idx] = {
                                "id": delta.id or f"sub_call_{idx}",
                                "type": "function",
                                "function": {"name": delta.name or "", "arguments": delta.arguments or ""},
                            }
                        else:
                            if delta.name:
                                tool_calls_dict[idx]["function"]["name"] += delta.name
                            if delta.arguments:
                                tool_calls_dict[idx]["function"]["arguments"] += delta.arguments

                if anim._running:
                    await anim.stop()

                if thinking_header_printed:
                    ui.console.print("\n[dim #a855f7]╰────────────────────────────────╯[/dim #a855f7]\n")
                    thinking_header_printed = False

                if thinking_text.strip():
                    self.thinking_history.append(thinking_text.strip())

            except LLMError as e:
                if anim._running:
                    await anim.stop()

                # Reconnection retry on the SAME MODEL if temporary error occurs (no model switching)
                err_msg = str(e).lower()
                is_transient = any(term in err_msg for term in ("429", "rate limit", "timed out", "timeout", "network error", "busy", "502", "503", "504"))
                if is_transient and not assistant_text and reconnect_attempts < 3:
                    reconnect_attempts += 1
                    delay = reconnect_attempts * 3.0
                    ui.print_warning(
                        f"\n⚠️  Subagent [{self.name}] connection/rate limit pause on '{self.config.model}'.\n"
                        f"🔄 Reconnecting to '{self.config.model}' (Attempt {reconnect_attempts}/3) in {delay:.1f}s...\n"
                    )
                    await asyncio.sleep(delay)
                    continue

                ui.print_error(f"Subagent [{self.name}] LLM error: {e}")
                self.status = "error"
                self.last_active = time.time()
                return SubagentResult(
                    role=self.role,
                    task=task,
                    success=False,
                    summary=f"Failed with LLM error: {e}",
                    tool_calls_count=tool_calls_count,
                    model=self.config.model,
                    provider=self.config.provider,
                )
            except Exception as e:
                if anim._running:
                    await anim.stop()
                ui.print_error(f"Subagent [{self.name}] unexpected error: {e}")
                self.status = "error"
                self.last_active = time.time()
                return SubagentResult(
                    role=self.role,
                    task=task,
                    success=False,
                    summary=f"Subagent error: {e}",
                    tool_calls_count=tool_calls_count,
                    model=self.config.model,
                    provider=self.config.provider,
                )

            formatted_calls = list(tool_calls_dict.values())
            if not formatted_calls and assistant_text:
                from cord.core.tool_parser import parse_fallback_tool_calls, strip_tool_xml_from_text
                recovered = parse_fallback_tool_calls(assistant_text, self.tools.tools)
                if recovered:
                    formatted_calls = recovered
                    assistant_text = strip_tool_xml_from_text(assistant_text, recovered)

            # Build message entry
            msg_obj: Dict[str, Any] = {"role": "assistant", "content": assistant_text or ""}
            if formatted_calls:
                msg_obj["tool_calls"] = formatted_calls
            self.messages.append(msg_obj)

            # If no tool calls, this is the final answer!
            if not formatted_calls:
                final_summary = assistant_text
                # Fallback synthesis if model returned empty text but executed tools
                if not final_summary.strip() and tool_calls_count > 0:
                    tool_outputs = [
                        m.get("content", "")[:200]
                        for m in self.messages
                        if m.get("role") == "tool" and m.get("name") not in ("think", "thought", "reasoning")
                    ]
                    final_summary = f"Executed {tool_calls_count} operations:\n" + "\n".join(tool_outputs[-4:])
                break

            # Execute tool calls
            for tc in formatted_calls:
                tool_calls_count += 1
                fn = tc.get("function", {})
                t_name = fn.get("name", "")
                raw_args = fn.get("arguments", "{}")
                try:
                    t_args = json.loads(raw_args) if raw_args else {}
                except json.JSONDecodeError:
                    t_args = {}

                # Intercept pseudo-reasoning tools (think, thought, reasoning)
                if t_name in ("think", "thought", "reasoning", "internal_thought"):
                    res_str = "Thought acknowledged. Please proceed directly with user response or real tool calls."
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id"),
                        "name": t_name,
                        "content": res_str,
                    })
                    continue

                # Resolve tool instance (canonical or alias)
                resolved_name = TOOL_ALIASES.get(t_name, t_name)
                tool_inst = self.tools.get(resolved_name) or self.tools.get(t_name)

                args_preview = str(t_args)[:60]
                ui.print_tool_start(f"[{self.name}] {t_name}", args_preview)

                if not tool_inst:
                    res_str = f"Error: Tool '{t_name}' not available to subagent."
                else:
                    try:
                        exec_fn = tool_inst.execute
                        if inspect.iscoroutinefunction(exec_fn):
                            res = await exec_fn(**t_args)
                        else:
                            res = exec_fn(**t_args)
                            if inspect.iscoroutine(res):
                                res = await res

                        if hasattr(res, "to_string"):
                            res_str = res.to_string()
                        elif isinstance(res, dict):
                            res_str = json.dumps(res, ensure_ascii=False)
                        else:
                            res_str = str(res)
                    except Exception as ex:
                        res_str = f"Error executing tool: {ex}"

                ui.print_tool_result(f"[{self.name}] {t_name}", success="Error" not in res_str, snippet=res_str[:160])

                self.tool_history.append({
                    "tool": t_name,
                    "args": t_args,
                    "result": res_str,
                    "success": "Error" not in res_str,
                    "timestamp": time.time(),
                })

                # Append tool response
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id"),
                    "name": t_name,
                    "content": res_str,
                })

        self.status = "completed"
        self.last_active = time.time()
        self.summary = final_summary or "Subagent completed its assigned steps."
        self.total_tool_calls += tool_calls_count

        ui.print_success(f"Subagent [{self.name}] completed task ({tool_calls_count} tool calls).")
        return SubagentResult(
            role=self.role,
            task=task,
            success=True,
            summary=self.summary,
            details=final_summary,
            tool_calls_count=tool_calls_count,
            model=self.config.model,
            provider=self.config.provider,
        )
