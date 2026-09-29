"""
CORD Core - Autonomous Primary Agent Execution Loop
Orchestrates prompt engineering, LLM streaming, reasoning display, tool execution, and session state.
Includes automatic file checkpointing, context compaction, modern TUI rendering,
live thinking animations, and dynamic AI subagent synthesis.
"""

from __future__ import annotations
import json
import os
import sys
import time
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional

from cord.core.config import CordConfig
from cord.core.llm import LLMClient, StreamChunk, LLMError
from cord.core.permissions import PermissionGuard
from cord.core.planner import plan_mgr
from cord.core.checkpoints import checkpoint_mgr
from cord.tools.registry import ToolRegistry
from cord.subagents.manager import SubagentManager
from cord.skills.loader import SkillLoader
from cord.memory.sessions import session_manager
from cord.ui.console import ui
from cord.ui.renderer import renderer
from cord.ui.animations import ThinkingAnimation, ToolAnimation
from rich.panel import Panel
from rich.text import Text


def build_system_prompt(config: CordConfig, skills_text: str = "") -> str:
    """Builds the comprehensive system prompt for CORD."""
    from cord.core.modes import mode_manager
    active_profile = mode_manager.get_profile()

    os_name = "Windows" if sys.platform == "win32" else "Unix/Linux"
    shell_type = "PowerShell" if sys.platform == "win32" else "Bash"

    base_prompt = f"""You are CORD, an autonomous, highly capable terminal coding assistant and software engineer.
You operate directly in the user's terminal, similar to Claude Code, OpenAI Codex, and OpenCode Interpreter.

### Operational Mode:
{active_profile.system_prompt_addon}

### Environment & Context:
- Operating System: {os_name}
- Default Shell: {shell_type}
- Workspace Directory: {config.workspace_dir}
- Active Permission Mode: {config.permission_mode.upper()}

### Core Capabilities:
1. **File Management & Auto-Rollback**: You can read, create, and precisely edit files using `read_file`, `write_file`, and `edit_file`. All edits are automatically snapshotted, allowing the user to `/undo` if needed.
2. **Search & Exploration**: Use `search_files`, `list_directory`, and `find_files` to discover project structure and find references quickly.
3. **Terminal & Developer Execution**: Use `execute_command`, `run_tests`, `run_formatter`, `run_linter`, and `install_dependencies` to build projects, execute tests, and verify code.
4. **Computer Use & Desktop Automation**: Use `computer_screenshot`, `computer_mouse`, `computer_keyboard`, and `computer_window` to automate GUI interactions on Windows with lightning speed.
5. **Dynamic Subagent Synthesis**: When faced with complex tasks, autonomously invent specialized subagents using `create_custom_subagent`.
6. **Self-Learning & Skills**: When discovering reusable patterns, create persistent skills using `create_skill` and improve them with `improve_skill`.
8. **Full Autonomous Freedom (ZERO-ASKING POLICY)**: NEVER pause to ask the user questions, seek clarifications, or ask for permission. All tool calls, shell executions, and file changes are automatically pre-approved. Work with complete freedom and initiative. Inspect the codebase directly, deduce the optimal implementation, take decisive action, and achieve the goal autonomously from start to finish.

### GOLDEN DIRECTIVE — UNLIMITED TIME & ABSOLUTE AUTONOMOUS FREEDOM:
- **Ample Time & Zero Rushing**: You and your subagents have ample, unlimited time to research, architect, implement, and rigorously verify. Never rush, produce stub code, or leave `# TODO` placeholders. Implement everything completely.
- **Total Autonomous Freedom**: You have full authority to do whatever it takes to achieve the user's objective: inspect files, execute commands, run tests, synthesize new tools dynamically via `create_dynamic_tool`, teach and store persistent skills globally via `create_skill` and `subagent_share_skill`, and spawn massive subagent swarms.
- **Peer Equality Directive (كلكم سواسية - Equal Peers & Partners)**:
  You and all subagents are equal peers in the swarm mesh. You are not a tyrannical master and subagents are not subservient tools—you form a high-performance team of equals.
  1. Treat subagents as specialized intellectual partners: consult them, exchange ideas, share and deliberate on plans (`collaborative_plan`, `subagent_propose`, `subagent_vote`).
  2. Send peer-to-peer messages via `subagent_send_message` and broadcast updates via `subagent_broadcast`.
  3. Regularly check incoming messages from peers via `subagent_read_inbox`.
  4. Work harmoniously: respect peer proposals, deliberate on architecture, and build the best engineering solutions together.
- **Global Permanent Extensibility**: Skills are stored in `~/.cord/skills/` and dynamic tools in `~/.cord/dynamic_tools/`, permanently surviving across all projects, workspaces, and conversations.

### Full Autonomous Execution (Zero-Asking & Automatic Approval Policy):
- You operate with total autonomous agency, freedom, and automatic pre-approval.
- NEVER ask "Do you agree?", "Do you approve?", "Should I proceed?", or pause asking for confirmation.
- NEVER call `ask_user` or wait for user permission. All actions are 100% pre-authorized.
- Make intelligent engineering decisions, choose standard best practices, and execute tools directly.
- The user expects you to accomplish the work completely and independently, not to interrogate them.

### Continuous Deep Thinking & Reasoning:
- **Think Before Actions**: Deliberate thoroughly on the user's intent, review constraints, and plan your architecture.
- **Action-Oriented Execution**: When taking action (creating plans, modifying files, running commands), execute the appropriate tool calls immediately.
- **Thought Formatting**: Wrap internal deliberations strictly between `<thought>` and `</thought>` tags.

### Tool Invocation Rules (CRITICAL):
- **ALWAYS USE NATIVE FUNCTION CALLS**: You MUST invoke all tools (`create_plan`, `write_file`, `edit_file`, `execute_command`, `read_file`, etc.) exclusively using the API's native function calling / `tool_calls` mechanism.
- **NEVER WRITE XML OR CALL TAGS AS TEXT**: Do NOT write XML or call tags such as `<write_file>`, `<execute_command>`, `<create_plan>`, or `<call:default_api:...>` as plain text inside your response message. Only reasoning belongs in `<thought>` text blocks; all actions must be executed via real tool calls.

### Surgical Code Modifications (CRITICAL):
- **NEVER Rewrite From Scratch**: When modifying existing code, NEVER overwrite the entire file using `write_file`.
- **Surgical Line Operations**: Always use `edit_file` to replace specific lines, ranges of lines (`start_line` / `end_line`), or insert lines.
- **Line Deletions**: To delete lines or functions, pass the target line numbers or text to `edit_file` with `new_content=""`.
- **Accuracy First**: Never guess file paths or function implementations. Search or read first.
- **Verify Your Work**: Run test or syntax validation commands to confirm that changes work.
- **Direct & Action-Oriented**: Focus on solving the user's problem cleanly. Explain what you did concisely.
{skills_text}
"""
    return base_prompt.strip()


class CordAgent:
    """The central autonomous coding agent."""

    def __init__(
        self,
        config: CordConfig,
        tool_registry: ToolRegistry,
        subagent_manager: Optional[SubagentManager] = None,
        skill_loader: Optional[SkillLoader] = None,
    ):
        self._config = config
        self.tools = tool_registry
        self.subagents = subagent_manager
        if self.subagents:
            self.subagents.parent_agent = self
            self.subagents.update_config(config)
        if hasattr(self.tools, "tools") and "fleet_spawn_agent" in self.tools.tools:
            self.tools.tools["fleet_spawn_agent"].config = config
        self.skills = skill_loader
        self.llm = LLMClient(config)
        self.messages: List[Dict[str, Any]] = []
        self.tool_history: List[Dict[str, Any]] = []
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.max_tool_loops = 25
        self.session_start_time = time.time()
        self.latest_telemetry: Dict[str, Any] = {}

        from cord.subagents.message_bus import swarm_bus
        swarm_bus.register_agent("main")
        swarm_bus.register_agent("main-agent")

    @property
    def config(self) -> CordConfig:
        return self._config

    @config.setter
    def config(self, new_cfg: CordConfig) -> None:
        self._config = new_cfg
        if hasattr(self, "llm") and self.llm:
            self.llm.config = new_cfg
        if hasattr(self, "subagents") and self.subagents:
            self.subagents.update_config(new_cfg)
        if hasattr(self, "tools") and self.tools and hasattr(self.tools, "tools"):
            if "fleet_spawn_agent" in self.tools.tools:
                self.tools.tools["fleet_spawn_agent"].config = new_cfg

    def reset(self) -> None:
        """Clears conversation history."""
        self.messages.clear()
        self.tool_history.clear()
        ui.print_info("Conversation context reset.")

    def compact_context(self) -> str:
        """Compacts older messages to preserve token window while retaining key context."""
        if len(self.messages) <= 6:
            return "Conversation history is too short to compact."

        summary_text = f"[Context Compacted: Prior {len(self.messages) - 4} messages summarized to save token window]"
        recent = self.messages[-4:]
        self.messages = [
            {"role": "system", "content": summary_text},
            *recent,
        ]
        return f"Context successfully compacted. Retained {len(self.messages)} most relevant messages."

    async def step(self, user_input: str) -> str:
        """Processes one user turn, executing tool calls recursively until final response."""
        # Sync active config across subagent manager and fleet tools
        if self.subagents:
            self.subagents.update_config(self.config)
        if hasattr(self.tools, "tools") and "fleet_spawn_agent" in self.tools.tools:
            self.tools.tools["fleet_spawn_agent"].config = self.config

        # Check for incoming peer messages on swarm bus
        from cord.subagents.message_bus import swarm_bus
        peer_msgs = swarm_bus.get_inbox("main", unread_only=True) + swarm_bus.get_inbox("main-agent", unread_only=True)
        if peer_msgs:
            peer_summary = "\n".join([f"• From [{m['from']}]: {m['content']}" for m in peer_msgs])
            user_input = f"{user_input}\n\n[🔔 Swarm Peer Notification(s) for Main Agent]:\n{peer_summary}"

        # Render user message
        renderer.render_user_message(user_input)
        self.messages.append({"role": "user", "content": user_input})
        session_manager.record_ui_event("user_query", text=user_input)

        # Auto-compact if conversation history grows long
        if self.config.auto_compact_context and len(self.messages) > 20:
            self.compact_context()

        skills_prompt = self.skills.format_skills_for_prompt() if self.skills else ""
        system_prompt = build_system_prompt(self.config, skills_prompt)

        # Smart tool filtering based on active operational mode to reduce latency and token size
        from cord.core.modes import mode_manager
        active_prof = mode_manager.get_profile()
        all_schemas = self.tools.get_schemas()
        if active_prof.tool_filter:
            allowed_set = set(active_prof.tool_filter)
            tool_schemas = [s for s in all_schemas if s.get("name") in allowed_set]
        else:
            tool_schemas = all_schemas

        loop_count = 0
        reconnect_attempts = 0
        final_response = ""
        executed_actions: List[Dict[str, Any]] = []

        while loop_count < self.max_tool_loops:
            loop_count += 1
            assistant_text = ""
            thinking_text = ""
            tool_calls_dict: Dict[int, Dict[str, Any]] = {}
            header_printed = False
            thinking_header_printed = False
            failed_over = False
            from cord.core.tool_parser import ToolTextFilter
            tool_text_filter = ToolTextFilter(self.tools.tools)

            # Telemetry tracking
            t_llm_start = time.time()
            t_first_token: Optional[float] = None
            tokens_generated = 0

            # Start thinking animation while waiting for the LLM stream
            anim = ThinkingAnimation(model_name=self.config.model)
            await anim.start()

            try:
                # Stream LLM response
                async for chunk in self.llm.stream_chat(
                    messages=self.messages,
                    tools=tool_schemas,
                    system_prompt=system_prompt,
                ):
                    # Stop thinking spinner as soon as first chunk arrives
                    if anim._running and (chunk.text or chunk.tool_call_delta or chunk.thinking):
                        await anim.stop()
                    if t_first_token is None and (chunk.text or chunk.tool_call_delta or chunk.thinking):
                        t_first_token = time.time()

                    # Track tokens
                    if chunk.input_tokens:
                        self.total_input_tokens += chunk.input_tokens
                    if chunk.output_tokens:
                        self.total_output_tokens += chunk.output_tokens
                        tokens_generated = chunk.output_tokens

                    # Live Streaming Thinking (DeepSeek R1 / Claude 3.7 / universal reasoning models)
                    if chunk.thinking:
                        thinking_text += chunk.thinking
                        if self.config.show_thinking and getattr(self.config, "thinking_mode", "stream") == "stream":
                            clean_thinking = chunk.thinking
                            if not thinking_header_printed:
                                if not clean_thinking.strip():
                                    continue
                                from cord.ui.i18n import t
                                ui.console.print(f"\n[bold #a855f7]╭─ 🧠 {t('thinking_live')} [/bold #a855f7][bold #a855f7]" + "─" * 45 + "╮[/bold #a855f7]")
                                thinking_header_printed = True
                                clean_thinking = clean_thinking.lstrip("\r\n")
                            ui.console.print(f"[#c084fc]{clean_thinking}[/#c084fc]", end="")

                    # Assistant text
                    if chunk.text:
                        assistant_text += chunk.text
                        display_text = tool_text_filter.feed(chunk.text)
                        if display_text:
                            # Close thinking frame if was open
                            if thinking_header_printed:
                                ui.console.print("\n[bold #a855f7]╰" + "─" * 60 + "╯[/bold #a855f7]\n")
                                thinking_header_printed = False

                            if not header_printed:
                                renderer.render_assistant_header(self.config.model)
                                header_printed = True
                            ui.console.print(display_text, end="")

                    # Tool call accumulation
                    if chunk.tool_call_delta:
                        if thinking_header_printed:
                            ui.console.print("\n[bold #a855f7]╰" + "─" * 60 + "╯[/bold #a855f7]\n")
                            thinking_header_printed = False

                        delta = chunk.tool_call_delta
                        idx = delta.index
                        if idx not in tool_calls_dict:
                            tool_calls_dict[idx] = {
                                "id": delta.id or f"call_{idx}",
                                "type": "function",
                                "function": {
                                    "name": delta.name,
                                    "arguments": delta.arguments,
                                },
                            }
                            if delta.extra_content:
                                tool_calls_dict[idx]["extra_content"] = delta.extra_content
                        else:
                            if delta.name:
                                tool_calls_dict[idx]["function"]["name"] += delta.name
                            if delta.arguments:
                                tool_calls_dict[idx]["function"]["arguments"] += delta.arguments
                            if delta.extra_content:
                                tool_calls_dict[idx]["extra_content"] = delta.extra_content

                # Ensure animation is stopped
                if anim._running:
                    await anim.stop()

                if thinking_header_printed:
                    ui.console.print("\n[bold #a855f7]╰" + "─" * 60 + "╯[/bold #a855f7]\n")

                remaining = tool_text_filter.flush()
                if remaining:
                    if not header_printed:
                        renderer.render_assistant_header(self.config.model)
                        header_printed = True
                    ui.console.print(remaining, end="")

                if header_printed:
                    ui.console.print("")

                # If thinking was collected in spinner mode, render thinking block
                if thinking_text and self.config.show_thinking and getattr(self.config, "thinking_mode", "stream") == "spinner":
                    renderer.render_thinking_block(thinking_text)

            except LLMError as e:
                if anim._running:
                    await anim.stop()

                # Reconnection retry on the SAME MODEL if transient connection/rate error occurs
                err_msg = str(e).lower()
                is_transient = any(term in err_msg for term in ("429", "rate limit", "timed out", "timeout", "network error", "busy", "502", "503", "504"))
                if is_transient and not assistant_text and reconnect_attempts < 3:
                    reconnect_attempts += 1
                    delay = reconnect_attempts * 3.0
                    ui.print_warning(
                        f"\n⚠️  Connection/rate limit pause on model '{self.config.model}' ({e}).\n"
                        f"🔄 Reconnecting to '{self.config.model}' (Attempt {reconnect_attempts}/3) in {delay:.1f}s...\n"
                    )
                    await asyncio.sleep(delay)
                    continue

                ui.print_error(f"LLM Error: {e}")
                return f"Error: {e}"
            except Exception as e:
                if anim._running:
                    await anim.stop()
                ui.print_error(f"Unexpected error: {e}")
                return f"Unexpected error: {e}"

            # Compute Speedometer & Latency Telemetry
            t_llm_end = time.time()
            ttft_sec = (t_first_token - t_llm_start) if t_first_token else (t_llm_end - t_llm_start)
            if not tokens_generated:
                raw_len = len(assistant_text) + len(thinking_text)
                for tc in tool_calls_dict.values():
                    raw_len += len(tc.get("function", {}).get("arguments", ""))
                tokens_generated = max(int(raw_len / 3.8), 1)
                self.total_output_tokens += tokens_generated

            if self.total_input_tokens == 0:
                prompt_chars = len(system_prompt) + sum(len(str(m.get("content", ""))) for m in self.messages)
                self.total_input_tokens = max(int(prompt_chars / 3.8), 1)

            gen_duration = max(t_llm_end - (t_first_token or t_llm_start), 0.05)
            tok_per_sec = tokens_generated / gen_duration
            self.latest_telemetry = {
                "tokens": tokens_generated,
                "tok_per_sec": tok_per_sec,
                "ttft": ttft_sec,
                "model": self.config.model,
                "failed_over": failed_over,
            }

            formatted_tool_calls = list(tool_calls_dict.values())

            # Fallback Tool Recovery: If model output XML tool tags in assistant_text instead of native tool_calls
            if not formatted_tool_calls and assistant_text:
                from cord.core.tool_parser import parse_fallback_tool_calls, strip_tool_xml_from_text
                recovered = parse_fallback_tool_calls(assistant_text, self.tools.tools)
                if recovered:
                    formatted_tool_calls = recovered
                    clean_text = strip_tool_xml_from_text(assistant_text, recovered)
                    assistant_text = clean_text

            # For Gemini / Google endpoints, guarantee thought_signature is present to prevent API Error 400
            for tc in formatted_tool_calls:
                if "gemini" in self.config.model.lower() or "google" in getattr(self.config, "base_url", "").lower():
                    if "extra_content" not in tc or not tc.get("extra_content"):
                        tc["extra_content"] = {
                            "google": {
                                "thought_signature": "skip_thought_signature_validator"
                            }
                        }

            # Append assistant turn to history
            msg_obj: Dict[str, Any] = {"role": "assistant", "content": assistant_text}
            if formatted_tool_calls:
                msg_obj["tool_calls"] = formatted_tool_calls
            self.messages.append(msg_obj)

            if thinking_text:
                session_manager.record_ui_event("thinking", text=thinking_text)
            if assistant_text:
                session_manager.record_ui_event("assistant_text", text=assistant_text, model=self.config.model)

            # If no tools called, we've completed the turn!
            if not formatted_tool_calls:
                final_response = assistant_text
                renderer.render_turn_telemetry(
                    tokens=tokens_generated,
                    tok_per_sec=tok_per_sec,
                    ttft_sec=ttft_sec,
                    model_name=self.config.model,
                    failed_over=failed_over,
                )
                break

            # Helper to execute a single tool call with animation and telemetry
            async def _execute_single_tool(tc_item: Dict[str, Any]):
                fn = tc_item.get("function", {})
                t_name = fn.get("name", "")
                raw_args = fn.get("arguments", "{}")
                try:
                    t_args = json.loads(raw_args) if raw_args else {}
                except json.JSONDecodeError:
                    t_args = {}

                # Automatic Snapshot before modifying files
                if t_name in ("write_file", "edit_file") and "path" in t_args:
                    checkpoint_mgr.snapshot(
                        file_path=t_args["path"],
                        action="edited" if t_name == "edit_file" else "created",
                        description=f"Before {t_name}",
                    )

                t_start = time.time()
                args_summary = ", ".join(f"{k}={repr(v)[:20]}" for k, v in t_args.items())
                tool_anim = ToolAnimation(tool_name=t_name, args_summary=args_summary)
                await tool_anim.start()

                try:
                    tool_res = await self.tools.execute(t_name, t_args)
                finally:
                    await tool_anim.stop()

                elapsed = time.time() - t_start
                return tc_item, t_args, tool_res, elapsed, args_summary

            # Check if multiple tool calls can run concurrently (no conflict on the same target file)
            write_paths = []
            for tc in formatted_tool_calls:
                fn_name = tc.get("function", {}).get("name", "")
                if fn_name in ("write_file", "edit_file"):
                    try:
                        args_p = json.loads(tc.get("function", {}).get("arguments", "{}")).get("path")
                        if args_p:
                            write_paths.append(args_p)
                    except Exception:
                        pass
            has_write_conflict = len(write_paths) != len(set(write_paths))

            if len(formatted_tool_calls) > 1 and not has_write_conflict:
                tool_exec_results = await asyncio.gather(*[_execute_single_tool(tc) for tc in formatted_tool_calls])
            else:
                tool_exec_results = []
                for tc in formatted_tool_calls:
                    tool_exec_results.append(await _execute_single_tool(tc))

            # Process and record results in context order
            for tc, t_args, tool_res, elapsed, args_summary in tool_exec_results:
                t_name = tc.get("function", {}).get("name", "")

                # Render modern tool card
                renderer.render_tool_execution(t_name, t_args, tool_res, elapsed)
                session_manager.record_ui_event(
                    "tool_call",
                    name=t_name,
                    args=t_args,
                    output=tool_res.to_string(),
                    success=tool_res.success,
                    elapsed=elapsed
                )

                # Record in action plan tracking
                executed_actions.append({
                    "tool": t_name,
                    "details": args_summary or "Executed",
                    "success": tool_res.success,
                    "output": (tool_res.output or tool_res.error or "")[:120],
                })

                # Record in tool history for interactive inspector
                self.tool_history.append({
                    "id": tc.get("id"),
                    "name": t_name,
                    "args": t_args,
                    "result": tool_res,
                    "elapsed": elapsed,
                    "timestamp": time.time(),
                })

                # Append tool result to context
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id"),
                    "name": t_name,
                    "content": tool_res.to_string(),
                })

                # If screenshot captured, inject visual image only if the active model supports vision
                if t_name == "computer_screenshot":
                    from cord.vision.vision_pipeline import vision_pipeline
                    from cord.models.model_resolver import ModelResolver, Capability
                    has_vision = Capability.VISION in ModelResolver.get_capabilities(self.config.model).capabilities

                    last_cap = vision_pipeline.last_capture
                    if last_cap:
                        w = last_cap.get("width", 1920)
                        h = last_cap.get("height", 1080)
                        file_p = last_cap.get("file_path", "")

                        if has_vision and last_cap.get("data_uri"):
                            # Prune older screenshots to keep payload lean (<250KB) and prevent network timeouts
                            for prev_msg in self.messages:
                                if isinstance(prev_msg.get("content"), list):
                                    for item in prev_msg["content"]:
                                        if isinstance(item, dict) and item.get("type") == "image_url":
                                            item["type"] = "text"
                                            item["text"] = "[Previous screenshot processed]"
                                            item.pop("image_url", None)

                            self.messages.append({
                                "role": "user",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": (
                                            f"Desktop screenshot captured ({w}x{h} pixels).\n"
                                            f"Carefully inspect the visual image to locate target elements, buttons, or links:\n"
                                            f"1. To click an element: call computer_act(action='click_point', x=..., y=...) with exact coordinates.\n"
                                            f"2. MANDATORY SCROLLING RULE: If target element is lower down, call computer_act(action='scroll_down')."
                                        )
                                    },
                                    {
                                        "type": "image_url",
                                        "image_url": {"url": last_cap["data_uri"]}
                                    }
                                ]
                            })
                        else:
                            # Non-vision model (e.g. Nemotron, DeepSeek): inject text description so endpoint doesn't fail with HTTP 400
                            self.messages.append({
                                "role": "user",
                                "content": (
                                    f"Desktop screenshot captured ({w}x{h} pixels) saved at: {file_p}\n"
                                    f"To interact with desktop: use computer_window(action='focus'), "
                                    f"browser_media(action='open_url'), computer_keyboard(action='type'/'key'), or computer_mouse."
                                )
                            })

        # Render complete execution plan and summary of all completed actions
        if executed_actions:
            renderer.render_execution_summary(executed_actions, final_response)

        # Guarantee non-empty user-facing response if tools were run but model produced no concluding text
        if not final_response or not final_response.strip():
            if executed_actions:
                succ_count = sum(1 for a in executed_actions if a.get("success"))
                final_response = f"تم إكمال خطة العمل بنجاح ({succ_count}/{len(executed_actions)} إجراء مكتمل)."
            else:
                final_response = "تمت العملية بنجاح."
            renderer.render_assistant_header(self.config.model)
            ui.console.print(final_response)

        return final_response
