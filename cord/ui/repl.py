"""
CORD UI - Interactive REPL & Slash Command System
Powered by prompt_toolkit with autocompletion, persistent history, dynamic status toolbar,
and slash commands for undo, export, compaction, themes, and session tracking.
"""

from __future__ import annotations
import os
import sys
import re
import time
import subprocess
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.key_binding import KeyBindings
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text

from cord.core.config import ConfigManager, CordConfig, PROVIDER_PRESETS, normalize_base_url
from cord.core.agent import CordAgent
from cord.core.planner import plan_mgr
from cord.core.checkpoints import checkpoint_mgr
from cord.mcp.manager import MCPManager
from cord.subagents.manager import SubagentManager
from cord.skills.loader import SkillLoader
from cord.ui.console import ui, THEMES
from cord.ui.settings_menu import show_settings_menu
from cord.tasks.task_manager import task_manager
from cord.vision.safety import computer_safety, ComputerSafetyLevel
from cord.cli.doctor import run_doctor
from cord.core.agent_runtime import AgentRuntime
from cord.core.modes import mode_manager, OperationalMode, MODE_PROFILES
from cord.memory.sessions import session_manager
from cord.ui.stats_panel import render_stats_dashboard, get_workspace_file_stats
from cord.ui.i18n import i18n, t, LANGUAGES
from cord.ui.welcome import show_first_run_language_wizard
from cord.utils.window_manager import window_manager
from cord.voice import audio_recorder, stt, tts, LiveVoiceSession

from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.shortcuts import CompleteStyle

SLASH_COMMAND_INFO = [
    ("/menu", "Interactive quick action dashboard"),
    ("/mode", "Switch mode (fast, computer, coder, agent)"),
    ("/scout", "Scout and benchmark modern AI models"),
    ("/models", "List saved AI model bookmarks"),
    ("/model", "Switch or bookmark model (/model <name>)"),
    ("/update-models", "Register newest AI models"),
    ("/computer", "Inspect/set Computer-Use level"),
    ("/stop", "Emergency Kill Switch"),
    ("/stats", "Codebase statistics & analytics"),
    ("/sessions", "Saved conversation sessions"),
    ("/resume", "Resume a previous conversation"),
    ("/new", "Start fresh conversation session"),
    ("/undo", "Undo last file change"),
    ("/plan", "View active plan"),
    ("/tools", "List registered native tools"),
    ("/tasks", "Hierarchical task tree"),
    ("/doctor", "System diagnostics check"),
    ("/settings", "Interactive settings editor"),
    ("/lang", "Change interface language"),
    ("/input", "Toggle input engine (advanced/native)"),
    ("/thinking", "Toggle thinking mode (stream/spinner/off)"),
    ("/theme", "Switch TUI theme"),
    ("/compact", "Compact context memory"),
    ("/export", "Export transcript to Markdown"),
    ("/cost", "Session token usage & cost"),
    ("/diff", "View git diff"),
    ("/yolo", "Autonomous YOLO mode"),
    ("/strict", "Strict prompt for all tools"),
    ("/balanced", "Balanced permission mode"),
    ("/live", "Hands-Free Live Voice Agent Mode"),
    ("/mic", "Record voice audio & transcribe into input (Alt+M or F2)"),
    ("/hide", "Stealth: Hide terminal window"),
    ("/show", "Restore terminal window to foreground"),
    ("/tts", "Speak text aloud or toggle TTS (/tts on|off)"),
    ("/fleet", "Inspect & manage remote SSH machines"),
    ("/cron", "Scheduled background automation tasks"),
    ("/ollama", "Inspect, pull & switch local Ollama models"),
    ("/voice", "Configure voice synthesis provider & API keys"),
    ("/provider", "Manage custom & preset AI providers (/provider list|add|delete|use|test)"),
    ("/window", "In-terminal multi-window multiplexer (/window split|switch|close|resize)"),
    ("/split", "Toggle multi-pane sidebar dashboard (Ctrl+S)"),
    ("/swarm", "Inspect 10,000+ agent swarm mesh status"),
    ("/copy", "Copy last response or code block to clipboard (/copy [code|all])"),
    ("/mouse", "Toggle native mouse text selection & scrolling (/mouse [on|off|native])"),
    ("/about", "Show animated system specifications, features & GitHub repo link"),
    ("/help", "Display help reference"),
    ("/exit", "Exit CORD CLI"),
]

SLASH_COMMANDS = [cmd for cmd, _ in SLASH_COMMAND_INFO]


class CordMentionAndCommandCompleter(Completer):
    """Provides instant popup autocompletion for '/' slash commands and '@' workspace mentions."""

    EXCLUDED_DIRS = {
        ".git", "__pycache__", "node_modules", ".venv", "venv", ".cord", ".pytest_cache",
        ".cache", "appdata", "application data", "local settings", "cookies", "recent",
        "sendto", "start menu", "templates", ".gemini", ".vscode", ".idea", "dist",
        "build", "target", "vendor", "bin", "obj", ".mypy_cache", ".tox",
        "system volume information", "$recycle.bin", ".npm", ".cargo", ".rustup",
        ".gradle", ".m2", ".conda", ".docker", ".antigravity", ".local", "temp", "tmp",
        "windows", "program files", "program files (x86)", "programdata",
    }

    def __init__(self, workspace_dir: str = ""):
        self.workspace_dir = workspace_dir
        self._cached_files: List[tuple[str, int]] = []
        self._cache_time: float = 0.0
        self._cache_root: str = ""
        self._ollama_cache_time: float = 0.0
        self._ollama_cached_models: List[Dict[str, Any]] = []

    def _get_workspace_files(self, root: Path) -> List[tuple[str, int]]:
        now = time.time()
        root_str = str(root.resolve()) if root.exists() else str(root)
        if self._cache_root == root_str and (now - self._cache_time) < 5.0:
            return self._cached_files

        collected: List[tuple[str, int]] = []
        if not root.exists() or not root.is_dir():
            self._cached_files = collected
            self._cache_time = now
            self._cache_root = root_str
            return collected

        # Detect if root is user home or root drive to protect against huge/circular trees
        is_home_or_root = False
        try:
            home_path = Path.home().resolve()
            resolved_root = root.resolve()
            if resolved_root == home_path or resolved_root.parent == resolved_root or len(resolved_root.parts) <= 2:
                is_home_or_root = True
        except Exception:
            pass

        # If user home or root drive, strictly search depth 1 (top-level files only)
        max_depth = 1 if is_home_or_root else 2
        max_files = 80
        t0 = time.perf_counter()
        time_limit_sec = 0.03  # 30ms strict UI-safety budget

        queue: List[tuple[Path, int]] = [(root, 0)]

        while queue and len(collected) < max_files:
            if (time.perf_counter() - t0) > time_limit_sec:
                break
            current_dir, depth = queue.pop(0)

            try:
                with os.scandir(current_dir) as it:
                    subdirs: List[Path] = []
                    for entry in it:
                        if (time.perf_counter() - t0) > time_limit_sec or len(collected) >= max_files:
                            break
                        try:
                            name_lower = entry.name.lower()
                            if entry.is_dir(follow_symlinks=False):
                                if entry.is_symlink():
                                    continue
                                if name_lower in self.EXCLUDED_DIRS or (name_lower.startswith(".") and not name_lower == ".cord"):
                                    continue
                                if depth + 1 < max_depth:
                                    subdirs.append(Path(entry.path))
                            elif entry.is_file(follow_symlinks=False):
                                try:
                                    rel = Path(entry.path).relative_to(root).as_posix()
                                except ValueError:
                                    rel = entry.name
                                try:
                                    size = entry.stat(follow_symlinks=False).st_size
                                except Exception:
                                    size = 0
                                collected.append((rel, size))
                        except (PermissionError, OSError):
                            continue
                    if depth + 1 < max_depth:
                        queue.extend((d, depth + 1) for d in subdirs)
            except (PermissionError, OSError):
                continue

        self._cached_files = collected
        self._cache_time = now
        self._cache_root = root_str
        return collected

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        stripped = text.lstrip()

        # 1. Slash commands at start of prompt
        if stripped.startswith("/") and " " not in stripped:
            query = stripped.lower()
            for cmd, desc in SLASH_COMMAND_INFO:
                if cmd.lower().startswith(query):
                    yield Completion(
                        cmd,
                        start_position=-len(query),
                        display=f"{cmd:<14}",
                        display_meta=desc,
                    )
            return

        # 2. Mentions with '@'
        match = re.search(r"@([a-zA-Z0-9_\./\\:-]*)$", text)
        if match:
            query = match.group(1).lower()
            start_pos = -len(match.group(0))

            # Preset mentions: @git, @tasks
            if "@git".startswith("@" + query):
                yield Completion("@git", start_position=start_pos, display="@git", display_meta="Inject active git diff & branch status")
            if "@tasks".startswith("@" + query):
                yield Completion("@tasks", start_position=start_pos, display="@tasks", display_meta="Inject active task hierarchy")

            # Active tasks from task_manager
            try:
                from cord.tasks.task_manager import task_manager
                for tid, t in list(task_manager.tasks.items())[:8]:
                    token = f"@task:{tid}"
                    if token.lower().startswith("@" + query):
                        yield Completion(token, start_position=start_pos, display=token, display_meta=f"{t.title[:25]} ({t.status.value})")
            except Exception:
                pass

            # Fleet Nodes
            try:
                from cord.fleet.manager import fleet_mgr
                for n in fleet_mgr.list_nodes()[:8]:
                    token = f"@node:{n.name}"
                    if token.lower().startswith("@" + query):
                        yield Completion(token, start_position=start_pos, display=token, display_meta=f"SSH ({n.user}@{n.host})")
            except Exception:
                pass

            # Scheduled Cron Jobs
            try:
                from cord.cron.cron_manager import cron_mgr
                for j in cron_mgr.list_jobs()[:8]:
                    token = f"@cron:{j.id}"
                    if token.lower().startswith("@" + query):
                        yield Completion(token, start_position=start_pos, display=token, display_meta=f"{j.name[:25]} ({j.schedule_expr})")
            except Exception:
                pass

            # Local Ollama Models (cached & only if query matches @ol or ollama)
            if "@ollama".startswith("@" + query) or query.startswith("ol"):
                now = time.time()
                if (now - self._ollama_cache_time) > 10.0:
                    self._ollama_cache_time = now
                    self._ollama_cached_models = []
                    try:
                        from cord.models.ollama_manager import ollama_mgr
                        if ollama_mgr.is_running(timeout_sec=0.1):
                            self._ollama_cached_models = ollama_mgr.list_models()[:8]
                    except Exception:
                        self._ollama_cached_models = []

                for m in self._ollama_cached_models:
                    token = f"@ollama:{m.get('name', '')}"
                    if token.lower().startswith("@" + query):
                        yield Completion(token, start_position=start_pos, display=token, display_meta=f"Local ({m.get('size', 'N/A')})")

            # Workspace files (cached, shallow, non-blocking)
            root = Path(self.workspace_dir or os.getcwd())
            files = self._get_workspace_files(root)
            count = 0
            for rel, size in files:
                if count >= 20:
                    break
                rel_lower = rel.lower()
                if not query or rel_lower.startswith(query) or query in rel_lower:
                    yield Completion(
                        f"@{rel}",
                        start_position=start_pos,
                        display=f"@{rel}",
                        display_meta=f"File ({size}B)",
                    )
                    count += 1


SlashCommandCompleter = CordMentionAndCommandCompleter


def get_git_branch(cwd: str) -> Optional[str]:
    """Retrieves the current git branch if in a git repo."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=1.0,
        )
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception:
        pass
    return None


class CordREPL:
    """Interactive command-line interface for CORD."""

    def __init__(
        self,
        config_mgr: ConfigManager,
        agent: CordAgent,
        mcp_manager: Optional[MCPManager] = None,
        subagent_manager: Optional[SubagentManager] = None,
        skill_loader: Optional[SkillLoader] = None,
    ):
        self.config_mgr = config_mgr
        self.agent = agent
        self.mcp = mcp_manager
        self.subagents = subagent_manager
        self.skills = skill_loader

        history_file = Path.home() / ".cord" / "history.txt"
        history_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Keybindings: multiline (Alt+Enter), Sessions (Alt+H), Microphone (Alt+M or F2), Split (Ctrl+S), Commands (Ctrl+P), Models (Ctrl+T)
        from prompt_toolkit.filters import has_completions

        kb = KeyBindings()

        @kb.add("escape", filter=has_completions)
        def _(event):
            event.current_buffer.cancel_completion()

        @kb.add("escape", "enter")
        def _(event):
            event.current_buffer.insert_text("\n")

        @kb.add("escape", "h")
        def _(event):
            event.app.exit(result="/sessions")

        @kb.add("escape", "m")
        def _(event):
            event.app.exit(result="/mic")

        @kb.add("f4")
        def _(event):
            event.app.exit(result="/mic")

        @kb.add("f2")
        def _(event):
            event.app.exit(result="/agents")

        @kb.add("c-a")
        def _(event):
            event.app.exit(result="/agents")

        @kb.add("escape", "a")
        def _(event):
            event.app.exit(result="/agents")

        @kb.add("c-s")
        def _(event):
            event.app.exit(result="/split")

        @kb.add("c-p")
        def _(event):
            event.app.exit(result="/menu")

        @kb.add("c-t")
        def _(event):
            event.app.exit(result="/models")

        @kb.add("c-w", "v")
        def _(event):
            event.app.exit(result="/window split v")

        @kb.add("c-w", "s")
        def _(event):
            event.app.exit(result="/window split h")

        @kb.add("c-w", "w")
        def _(event):
            event.app.exit(result="/window switch")

        @kb.add("c-w", "q")
        def _(event):
            event.app.exit(result="/window close")

        @kb.add("c-w", "+")
        def _(event):
            event.app.exit(result="/window resize +5")

        @kb.add("c-w", "-")
        def _(event):
            event.app.exit(result="/window resize -5")

        # mouse_support=False enables native terminal mouse selection, word highlighting,
        # copy-to-clipboard (right-click / Ctrl+C), and smooth mouse wheel scrolling up/down
        try:
            self.session = PromptSession(
                history=FileHistory(str(history_file)),
                completer=CordMentionAndCommandCompleter(config_mgr.config.workspace_dir),
                complete_while_typing=True,
                complete_style=CompleteStyle.COLUMN,
                key_bindings=kb,
                mouse_support=False,
            )
        except Exception:
            from prompt_toolkit.output import DummyOutput
            self.session = PromptSession(
                history=FileHistory(str(history_file)),
                completer=CordMentionAndCommandCompleter(config_mgr.config.workspace_dir),
                complete_while_typing=True,
                complete_style=CompleteStyle.COLUMN,
                key_bindings=kb,
                mouse_support=False,
                output=DummyOutput(),
            )

    def _resolve_mentions(self, text: str) -> str:
        """Finds @ mentions in user prompt and appends relevant context blocks."""
        matches = re.findall(r"@([a-zA-Z0-9_\./\\:-]+)", text)
        if not matches:
            return text

        root = Path(self.config_mgr.config.workspace_dir or os.getcwd())
        injected_context = []

        for m in set(matches):
            lower_m = m.lower()
            if lower_m == "git":
                branch = get_git_branch(str(root))
                try:
                    diff_res = subprocess.run(
                        ["git", "diff", "--stat"],
                        cwd=str(root),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                        text=True,
                        timeout=1.5,
                    )
                    diff_summary = diff_res.stdout.strip() or "No uncommitted changes."
                except Exception:
                    diff_summary = "Git diff unavailable."
                injected_context.append(f"\n[Context from @git - Branch: {branch or 'unknown'}]\n{diff_summary}")
                ui.print_info("Attached context from [bold cyan]@git[/bold cyan]")

            elif lower_m == "tasks":
                try:
                    from cord.tasks.task_manager import task_manager
                    tree_str = task_manager.render_tree()
                    injected_context.append(f"\n[Context from @tasks]\n{tree_str}")
                    ui.print_info("Attached context from [bold cyan]@tasks[/bold cyan]")
                except Exception:
                    pass

            elif lower_m.startswith("task:"):
                tid = m.split(":", 1)[1]
                try:
                    from cord.tasks.task_manager import task_manager
                    task = task_manager.get_task(tid)
                    if task:
                        injected_context.append(
                            f"\n[Context from @task:{tid}]\nTitle: {task.title}\nStatus: {task.status.value}\nDescription: {task.description}"
                        )
                        ui.print_info(f"Attached context from [bold cyan]@task:{tid}[/bold cyan]")
                except Exception:
                    pass

            elif lower_m.startswith("node:"):
                nname = m.split(":", 1)[1]
                try:
                    from cord.fleet.manager import fleet_mgr
                    node = fleet_mgr.get_node(nname)
                    if node:
                        injected_context.append(
                            f"\n[Context from @node:{nname}]\nMachine: {node.name}\nHost: {node.user}@{node.host}:{node.port}\nOS: {node.os_type}\nStatus: {node.status}\nTags: {', '.join(node.tags)}\nDescription: {node.description}"
                        )
                        ui.print_info(f"Attached context from [bold cyan]@node:{nname}[/bold cyan]")
                except Exception:
                    pass

            elif lower_m.startswith("cron:"):
                jid = m.split(":", 1)[1]
                try:
                    from cord.cron.cron_manager import cron_mgr
                    job = cron_mgr.get_job(jid)
                    if job:
                        injected_context.append(
                            f"\n[Context from @cron:{jid}]\nJob: {job.name}\nSchedule: {job.schedule_expr}\nTarget Node: {job.target_node}\nAction: {job.action_type}\nPrompt: {job.prompt}"
                        )
                        ui.print_info(f"Attached context from [bold cyan]@cron:{jid}[/bold cyan]")
                except Exception:
                    pass

            elif lower_m.startswith("ollama:"):
                oname = m.split(":", 1)[1]
                injected_context.append(
                    f"\n[Context from @ollama:{oname}]\nProvider: Ollama (Local)\nBase URL: http://localhost:11434/v1\nModel Tag: {oname}"
                )
                ui.print_info(f"Attached context from [bold cyan]@ollama:{oname}[/bold cyan]")

            elif lower_m.startswith("agent:") or lower_m.startswith("subagent:") or lower_m.startswith("peer:"):
                aname = m.split(":", 1)[1]
                if self.subagents:
                    ag = self.subagents.get_agent(aname)
                    if ag:
                        msgs_prev = "\n".join([f"  {msg.get('role')}: {str(msg.get('content'))[:120]}" for msg in ag.messages[-4:]])
                        injected_context.append(
                            f"\n[Context from Peer Subagent @{ag.name} ({ag.role})]\nStatus: {getattr(ag, 'status', 'idle')}\nModel: {ag.config.model} ({ag.config.provider})\nRecent transcript:\n{msgs_prev or '(no prior messages)'}"
                        )
                        ui.print_info(f"Attached context from subagent peer [bold cyan]@{ag.name}[/bold cyan]")

            else:
                # Check if file exists in workspace
                file_path = root / m
                if file_path.exists() and file_path.is_file():
                    try:
                        content = file_path.read_text(encoding="utf-8", errors="replace")
                        lines = content.splitlines()
                        if len(lines) > 250:
                            truncated = "\n".join(lines[:250]) + f"\n... [{len(lines)-250} more lines truncated] ..."
                        else:
                            truncated = content
                        injected_context.append(f"\n[Context from @{m} ({len(lines)} lines)]:\n```{file_path.suffix.lstrip('.')}\n{truncated}\n```")
                        ui.print_info(f"Attached context from file [bold cyan]@{m}[/bold cyan] ({min(len(lines), 250)} lines)")
                    except Exception as e:
                        ui.print_warning(f"Could not read referenced file @{m}: {e}")

        if injected_context:
            return text + "\n\n" + "\n".join(injected_context)
        return text

    def get_bottom_toolbar(self) -> HTML:
        cfg = self.config_mgr.config
        model_name = cfg.model.split("/")[-1]
        provider = cfg.provider.upper()
        from cord.core.modes import mode_manager
        cur_mode = mode_manager.current_mode.name.capitalize()
        active_sub_count = len(self.subagents.list_agents()) if self.subagents else 0
        swarm_badge = f' <style fg="#a855f7">🤖 {active_sub_count} peer(s)</style>' if active_sub_count else ''

        return HTML(
            f' <b><style fg="#38bdf8">⚡ CORD v1.4.0</style></b> │ <b><style fg="#ffffff">{model_name}</style></b> <style fg="#94a3b8">[{cur_mode} • {provider}]</style>{swarm_badge}\n'
            f' <style fg="#38bdf8">/about</style> <style fg="#cbd5e1">info</style> │ '
            f'<style fg="#38bdf8">f2/ctrl+a</style> <style fg="#cbd5e1">agents</style> │ '
            f'<style fg="#64748b">ctrl+t</style> models │ '
            f'<style fg="#64748b">ctrl+s</style> split │ '
            f'<style fg="#64748b">/settings</style> config │ '
            f'<style fg="#ef4444">ctrl+c</style> abort'
        )

    async def run(self) -> None:
        """Starts the interactive read-eval-print loop."""
        cfg = self.config_mgr.config

        # Ensure terminal has native mouse scrollback, mouse word selection, and alternate buffer disabled
        try:
            sys.stdout.write("\x1b[?1000l\x1b[?1002l\x1b[?1003l\x1b[?1006l\x1b[?1049l\x1b[?1007l")
            sys.stdout.flush()
        except Exception:
            pass

        # Respect user configured model and settings without auto-switching
        try:
            # First-Run Welcome Onboarding: choose language if not set
            if getattr(cfg, "language", None) is None:
                chosen = show_first_run_language_wizard(self.config_mgr)
                cfg.language = chosen
            else:
                i18n.set_language(cfg.language)

            ui.print_banner(model=cfg.model, provider=cfg.provider, mode=cfg.permission_mode)

            pt_style = Style.from_dict({
                "prompt": "bold #38bdf8",
                "bottom-toolbar": "bg:#0b192c fg:#38bdf8 bold",
            })

            # Launch cooperative background scheduler task
            cron_bg_task = asyncio.create_task(self._cron_poll_loop())

            while True:
                try:
                    # Determine active input engine
                    engine_pref = getattr(cfg, "input_engine", "auto")
                    is_native = (engine_pref == "native")

                    con_width = min(ui.console.width, 100) if ui.console.width else 80

                    # If split sidebar is enabled, render the side panel before prompting
                    from cord.ui.split_view import sidebar_state, render_sidebar_panel
                    from cord.ui.multipane import multipane_mgr
                    if sidebar_state.is_open:
                        panel = render_sidebar_panel(
                            tokens=self.agent.total_input_tokens + self.agent.total_output_tokens,
                            input_tokens=self.agent.total_input_tokens,
                            output_tokens=self.agent.total_output_tokens,
                            model=self.config_mgr.config.model,
                            mcp_mgr=self.mcp,
                            workspace_dir=self.config_mgr.config.workspace_dir,
                        )
                        ui.console.print(panel)

                    if multipane_mgr.is_split:
                        ui.console.print(multipane_mgr.render_multipane_layout())

                    # Render docked glowing blue box top border with electric blue accent
                    ui.console.print(
                        f"\n[bold #0284c7]╭─[/bold #0284c7][bold #38bdf8]── [bold white]💬 CORD PROMPT CONTAINER[/bold white] [/bold #38bdf8][dim]•[/dim] [dim white]Type prompt or instruction (type / for commands, @ for context)[/dim white]"
                    )

                    if is_native:
                        # Fallback native console input
                        user_input = ui.console.input("[bold #0284c7]│[/bold #0284c7] [bold cyan]cord[/bold cyan] [bold #38bdf8]❯[/bold #38bdf8] ")
                    else:
                        # Advanced prompt_toolkit with docked container & instant autocomplete popup
                        user_input = await self.session.prompt_async(
                            HTML("<b><style fg='#0284c7'>│ </style><style fg='#38bdf8'>❯</style></b> "),
                            placeholder=HTML("<style fg='#64748b'>Type your instructions or prompt here...</style>"),
                            bottom_toolbar=self.get_bottom_toolbar,
                            style=pt_style,
                        )

                    # Render Framed Input Bottom Border
                    ui.console.print("[bold #0284c7]╰" + "─" * (con_width - 1) + "╯[/bold #0284c7]")

                    text = user_input.strip()
                    if not text:
                        continue

                    # Handle slash commands
                    if text == "/":
                        await self._handle_slash_command("/menu")
                        continue
                    elif text.startswith("/"):
                        handled = await self._handle_slash_command(text)
                        if handled == "exit":
                            break
                        continue

                    # Natural language terminal stealth triggers
                    lower_text = text.lower().strip()
                    if lower_text in ("hide terminal", "hide console", "hide window", "minimize terminal"):
                        window_manager.hide_terminal()
                        ui.print_info("Terminal window hidden. CORD is running in stealth mode.")
                        continue
                    if lower_text in ("show terminal", "show console", "show window", "restore terminal"):
                        window_manager.show_terminal()
                        ui.print_info("Terminal window restored to foreground.")
                        continue

                    # Normal user query -> Resolve mentions and step agent
                    augmented_text = self._resolve_mentions(text)
                    if multipane_mgr.is_split:
                        multipane_mgr.active_pane.add_line(f"[bold cyan]User:[/bold cyan] {text}")
                        multipane_mgr.active_pane.status = "running"
                    ui.console.print()
                    res_step = await self.agent.step(augmented_text)
                    if multipane_mgr.is_split:
                        multipane_mgr.active_pane.status = "idle"
                        if res_step:
                            first_l = res_step.strip().splitlines()[0][:70]
                            multipane_mgr.active_pane.add_line(f"[bold green]CORD:[/bold green] {first_l}")
                    ui.console.print()

                except (KeyboardInterrupt, asyncio.CancelledError):
                    ui.print_warning("Interrupted by user. Type /exit to quit.")
                    continue
                except EOFError:
                    ui.print_info("Goodbye!")
                    break
                except Exception as e:
                    ui.print_error(f"Error in REPL loop: {e}")
        finally:
            if 'cron_bg_task' in locals() and not cron_bg_task.done():
                cron_bg_task.cancel()
            try:
                sys.stdout.write("\x1b[?1049l\x1b[?1007l")
                sys.stdout.flush()
            except Exception:
                pass

    async def _cron_poll_loop(self) -> None:
        """Background cooperative poll loop for scheduled tasks during interactive REPL."""
        from cord.cron.cron_manager import cron_mgr
        while True:
            try:
                await asyncio.sleep(20.0)
                due_jobs = cron_mgr.get_due_jobs()
                for job in due_jobs:
                    ui.console.print(
                        f"\n[bold yellow]⚡ [CRON BACKGROUND TRIGGER][/bold yellow] Running scheduled task: "
                        f"[bold white]{job.name}[/bold white] ({job.schedule_expr})"
                    )
                    await cron_mgr.execute_job(job.id, agent=self.agent)
            except asyncio.CancelledError:
                break
            except Exception:
                pass

    async def _handle_slash_command(self, cmd_text: str) -> Optional[str]:
        parts = cmd_text.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if cmd in ("/exit", "/quit"):
            ui.print_info("Exiting CORD CLI. Happy coding!")
            return "exit"

        elif cmd == "/help":
            self._print_help()

        elif cmd in ("/about", "/info", "/version"):
            from cord.ui.about import show_about_screen
            await show_about_screen(self.config_mgr.config, animated=True)

        elif cmd in ("/menu", "/dashboard"):
            from cord.ui.action_menu import show_interactive_action_menu
            show_interactive_action_menu(self)

        elif cmd in ("/scout", "/models-scout"):
            from cord.subagents.model_scout import ModelScoutSubagent
            scout = ModelScoutSubagent(self.config_mgr)
            scout.render_catalog_table(arg.strip() if arg else None)

        elif cmd in ("/update-models", "/refresh-models"):
            from cord.subagents.model_scout import ModelScoutSubagent
            scout = ModelScoutSubagent(self.config_mgr)
            count = scout.update_saved_models_in_config()
            ui.print_success(f"Model Scout registered/updated {count} frontier 2025/2026 models in ~/.cord/config.json!")
            scout.render_catalog_table()

        elif cmd in ("/lang", "/language"):
            if not arg:
                self._print_languages()
            else:
                if i18n.set_language(arg):
                    cfg = self.config_mgr.config
                    cfg.language = i18n.current_lang
                    self.config_mgr.save_global(cfg)
                    lang_name = f"{LANGUAGES[cfg.language]['flag']} {LANGUAGES[cfg.language]['name']}"
                    ui.print_success(t("language_set", lang=lang_name))
                else:
                    ui.print_warning(f"Unknown language code: '{arg}'. Available: ar, en, fr, es, de, zh, ja, ru, tr")

        elif cmd == "/input":
            cfg = self.config_mgr.config
            clean_arg = arg.strip().lower()
            if clean_arg in ("native", "1"):
                cfg.input_engine = "native"
            elif clean_arg in ("advanced", "pt", "2"):
                cfg.input_engine = "advanced"
            elif clean_arg in ("auto", "3"):
                cfg.input_engine = "auto"
            else:
                curr = getattr(cfg, "input_engine", "auto")
                cfg.input_engine = "advanced" if curr == "native" else "native"

            self.config_mgr.save_global(cfg)
            ui.print_success(t("input_mode_changed", mode=cfg.input_engine))

        elif cmd == "/thinking":
            cfg = self.config_mgr.config
            clean_arg = arg.strip().lower()
            if clean_arg in ("stream", "live", "1"):
                cfg.thinking_mode = "stream"
                cfg.show_thinking = True
            elif clean_arg in ("spinner", "2"):
                cfg.thinking_mode = "spinner"
                cfg.show_thinking = True
            elif clean_arg in ("off", "fast", "3"):
                cfg.thinking_mode = "off"
                cfg.show_thinking = False
            else:
                curr = getattr(cfg, "thinking_mode", "stream")
                cfg.thinking_mode = "off" if curr == "stream" else "stream"
                cfg.show_thinking = (cfg.thinking_mode != "off")

            self.config_mgr.save_global(cfg)
            ui.print_success(t("thinking_mode_changed", mode=cfg.thinking_mode))

        elif cmd == "/provider" and arg and arg.strip().lower() in PROVIDER_PRESETS:
            # Quick-switch shortcut: /provider <name> instantly switches provider
            key = arg.strip().lower()
            preset = PROVIDER_PRESETS[key]
            cfg = self.config_mgr.config
            cfg.provider = key
            cfg.base_url = preset.get("base_url", "")
            cfg.model = preset.get("default_model", "")
            cfg.api_format = preset.get("api_format", "openai")
            self.config_mgr.save_global(cfg)
            self.agent.config = cfg
            ui.print_success(f"Switched to [bold cyan]{preset['name']}[/bold cyan] (Model: {cfg.model})")

        elif cmd == "/settings":
            show_settings_menu(self.config_mgr)
            self.agent.config = self.config_mgr.config

        elif cmd == "/clear":
            self.agent.reset()
            ui.console.clear()
            cfg = self.config_mgr.config
            ui.print_banner(model=cfg.model, provider=cfg.provider, mode=cfg.permission_mode)

        elif cmd in ("/undo", "/rewind"):
            res = checkpoint_mgr.undo()
            if res:
                ui.print_success(f"[bold]Undo Completed:[/bold] {res}")
            else:
                ui.print_info("No file changes in history to undo.")

        elif cmd in ("/graph", "/code-graph"):
            from cord.core.code_graph import code_graph_engine
            code_graph_engine.render_overview()

        elif cmd in ("/impact", "/blast-radius"):
            from cord.core.code_graph import code_graph_engine
            target = arg.strip() if arg.strip() else "main.py"
            code_graph_engine.render_blast_radius(target)

        elif cmd in ("/sentinel", "/council", "/rfc"):
            from cord.subagents.sentinel import community_sentinel
            clean_arg = arg.strip()
            if clean_arg.startswith("triage "):
                topic = clean_arg[7:].strip()
                await community_sentinel.triage_proposal(
                    title=topic,
                    description=f"User proposed RFC: {topic}",
                    source="repl",
                )
            else:
                community_sentinel.render_overview()

        elif cmd in ("/radar", "/mcp-market"):
            from cord.core.tech_radar import tech_radar
            clean_arg = arg.strip()
            if clean_arg.startswith("install "):
                s_key = clean_arg[8:].strip()
                res = tech_radar.install_mcp_server(s_key)
                if res["success"]:
                    ui.print_success(res["message"])
                else:
                    ui.print_error(res["error"])
            else:
                tech_radar.render_radar()

        elif cmd == "/compact":
            msg = self.agent.compact_context()
            ui.print_success(msg)

        elif cmd == "/export":
            self._export_session()

        elif cmd in ("/changes", "/changelog", "/diffs"):
            from cord.ui.changes_dashboard import render_changes_dashboard
            render_changes_dashboard()

        elif cmd in ("/inspect", "/tools-history", "/inspector"):
            if arg.strip() and self.subagents and self.subagents.get_agent(arg.strip()):
                from cord.ui.subagent_viewer import open_subagent_monitor
                await open_subagent_monitor(self, self.subagents.get_agent(arg.strip()))
            else:
                from cord.ui.tool_inspector import launch_tool_inspector
                launch_tool_inspector(self.agent.tool_history)

        elif cmd == "/session":
            if arg.startswith("file "):
                tfile = arg[5:].strip()
                target_path = Path(tfile).expanduser().resolve()
                session_manager.set_target_file(str(target_path))
                ui.print_success(f"Session scoped to target file: [bold cyan]{target_path.name}[/bold cyan] ({target_path})")
            elif arg.strip() == "clear-file":
                session_manager.set_target_file(None)
                ui.print_success("Cleared file scope. Session is now global.")
            else:
                self._print_session_info()

        elif cmd in ("/fleet", "/ssh", "/nodes"):
            from rich.table import Table
            from cord.fleet.manager import fleet_mgr
            nodes = fleet_mgr.list_nodes()
            table = Table(title=f"🖥️  CORD Fleet SSH Machine Catalog ({len(nodes)} Nodes)", border_style="cyan")
            table.add_column("Node Name", style="bold cyan")
            table.add_column("Target Host", style="white")
            table.add_column("OS", style="green")
            table.add_column("Status", justify="center")
            table.add_column("Tags", style="yellow")
            table.add_column("Description", style="dim")
            for n in nodes:
                scolor = "bold green" if n.status == "online" else "yellow" if n.status == "configured" else "red"
                table.add_row(
                    n.name,
                    f"{n.user}@{n.host}:{n.port}",
                    n.os_type,
                    f"[{scolor}]{n.status}[/{scolor}]",
                    ", ".join(n.tags) if n.tags else "-",
                    n.description or "-",
                )
            ui.console.print(table)

        elif cmd in ("/cron", "/jobs", "/schedule"):
            from rich.table import Table
            from cord.cron.cron_manager import cron_mgr
            import time
            jobs = cron_mgr.list_jobs()
            table = Table(title=f"⏰ CORD Scheduled Background Tasks ({len(jobs)} Jobs)", border_style="yellow")
            table.add_column("Job ID", style="bold yellow")
            table.add_column("Name", style="bold white")
            table.add_column("Schedule", style="cyan")
            table.add_column("Target Node", style="magenta")
            table.add_column("Status", justify="center")
            table.add_column("Next Run", style="green")
            for j in jobs:
                next_s = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(j.next_run)) if j.next_run else "N/A"
                scolor = "bold green" if j.enabled else "dim"
                table.add_row(
                    j.id,
                    j.name,
                    j.schedule_expr,
                    j.target_node,
                    f"[{scolor}]{j.last_status}[/{scolor}]",
                    next_s,
                )
            ui.console.print(table)

        elif cmd in ("/ollama", "/local-models"):
            from rich.table import Table
            from cord.models.ollama_manager import ollama_mgr
            clean_arg = arg.strip()
            if clean_arg.startswith("pull "):
                m_to_pull = clean_arg[5:].strip()
                ui.print_info(f"Pulling Ollama model '{m_to_pull}' in background...")
                res = await ollama_mgr.pull_model(m_to_pull)
                if res["success"]:
                    ui.print_success(f"Successfully pulled '{m_to_pull}'! Switch with: /ollama {m_to_pull}")
                else:
                    ui.print_error(f"Failed to pull '{m_to_pull}': {res.get('error')}")
            elif clean_arg:
                cfg = ollama_mgr.switch_to_ollama(clean_arg, self.config_mgr)
                ui.print_success(f"Active model switched to local Ollama: [bold white]{cfg.model}[/bold white] ({cfg.base_url})")
            else:
                running = ollama_mgr.is_running()
                if not running:
                    ui.print_warning("Local Ollama daemon is OFFLINE at http://127.0.0.1:11434. Run 'ollama serve' to launch it.")
                else:
                    models = ollama_mgr.list_models()
                    table = Table(title=f"🦙 Local Ollama Models ({len(models)} Available)", border_style="cyan")
                    table.add_column("Model Name", style="bold cyan")
                    table.add_column("Size", style="green")
                    table.add_column("Digest", style="dim")
                    table.add_column("Modified", style="white")
                    for m in models:
                        table.add_row(m["name"], m["size"], m["digest"], m["modified_at"])
                    ui.console.print(table)
                    ui.console.print("Commands: [cyan]/ollama <name>[/cyan] (switch) │ [cyan]/ollama pull <name>[/cyan] (download)\n")

        elif cmd in ("/voice", "/tts-model"):
            from rich.table import Table
            from cord.voice.tts import tts
            from cord.voice.models import OPENAI_VOICES, ELEVENLABS_PRESET_VOICES
            clean_arg = arg.strip()
            parts = clean_arg.split()
            if parts and parts[0] == "test":
                phrase = " ".join(parts[1:]) if len(parts) > 1 else "Hello! CORD voice synthesizer test."
                ui.print_info(f"Playing test audio via {tts.config.provider} ({tts.config.voice_id})...")
                tts.speak(phrase, wait=False)
            elif parts and parts[0] in ("edge", "openai", "elevenlabs", "custom"):
                prov = parts[0]
                voice_id = parts[1] if len(parts) > 1 else None
                key = parts[2] if len(parts) > 2 else None
                tts.configure(provider=prov, voice_id=voice_id, api_key=key)
                ui.print_success(f"Voice synthesizer updated: provider=[bold cyan]{prov}[/bold cyan], voice=[bold yellow]{voice_id or tts.config.voice_id}[/bold yellow]")
            else:
                cfg = tts.config
                table = Table(title="🎙️  CORD Voice Models & TTS Engine", border_style="magenta")
                table.add_column("Setting", style="bold cyan")
                table.add_column("Current Value", style="bold white")
                table.add_row("Provider", cfg.provider.upper())
                table.add_row("Model", cfg.model)
                table.add_row("Voice ID", cfg.voice_id)
                table.add_row("Speed", f"{cfg.speed:.1f}x")
                table.add_row("API Key Configured", "✓ Yes" if cfg.api_key else "No (Edge-TTS or env)")
                ui.console.print(table)
                ui.console.print("Switch: [cyan]/voice edge <voice>[/cyan] │ [cyan]/voice openai <voice> [api_key][/cyan] │ [cyan]/voice elevenlabs <id> [api_key][/cyan]")
                ui.console.print("Test: [cyan]/voice test [phrase][/cyan]\n")

        elif cmd in ("/provider", "/providers"):
            from cord.models.provider_manager import provider_mgr
            parts = arg.strip().split()
            sub = parts[0].lower() if parts else "list"

            if sub == "list":
                all_provs = provider_mgr.list_providers(include_presets=True)
                table = Table(title=f"🌐 CORD AI Model Providers ({len(all_provs)} Available)", border_style="cyan")
                table.add_column("ID / Name", style="bold cyan")
                table.add_column("Type", style="bold white")
                table.add_column("Base URL", style="yellow")
                table.add_column("Default Model", style="green")
                table.add_column("API Format", style="magenta")
                table.add_column("Models Count", justify="center")
                for p in all_provs:
                    ptype = "[bold green]Custom[/bold green]" if p.get("is_custom") else "[dim]Preset[/dim]"
                    table.add_row(
                        p.get("name") or p.get("id"),
                        ptype,
                        p.get("base_url") or "(default)",
                        p.get("default_model") or "-",
                        p.get("api_format", "openai"),
                        str(len(p.get("models", []))),
                    )
                ui.console.print(table)
                ui.console.print("[dim]Commands: /provider add <name> <url> [key] [model] │ /provider delete <name> │ /provider use <name> │ /provider test <name>[/dim]\n")

            elif sub == "add":
                if len(parts) < 3:
                    ui.print_warning("Usage: /provider add <name> <base_url> [api_key] [default_model] [api_format]")
                else:
                    pname = parts[1]
                    purl = parts[2]
                    clean_purl, pnotice = normalize_base_url(purl)
                    if pnotice:
                        ui.print_info(f"[yellow]{pnotice}[/yellow]")
                    pkey = parts[3] if len(parts) > 3 and parts[3] != "none" else None
                    pmodel = parts[4] if len(parts) > 4 else "default"
                    pfmt = parts[5] if len(parts) > 5 else "openai"
                    res = provider_mgr.add_provider(
                        name=pname,
                        base_url=clean_purl,
                        api_key=pkey,
                        default_model=pmodel,
                        api_format=pfmt,
                    )
                    ui.print_success(f"Registered custom provider [bold cyan]{pname}[/bold cyan] ({clean_purl})")

            elif sub == "delete":
                if len(parts) < 2:
                    ui.print_warning("Usage: /provider delete <name>")
                else:
                    pname = parts[1]
                    if provider_mgr.delete_provider(pname):
                        ui.print_success(f"Deleted custom provider [bold red]{pname}[/bold red]")
                    else:
                        ui.print_warning(f"Could not delete provider '{pname}'. (Presets cannot be deleted)")

            elif sub == "test":
                if len(parts) < 2:
                    ui.print_warning("Usage: /provider test <name>")
                else:
                    pname = parts[1]
                    ui.print_info(f"Testing connectivity to '{pname}'...")
                    t_res = provider_mgr.test_provider(pname)
                    if t_res.get("success"):
                        ui.print_success(f"✔ Provider '{pname}' is reachable: {t_res.get('message')}")
                    else:
                        ui.print_error(f"❌ Provider '{pname}' failed: {t_res.get('error')}")

            elif sub == "use":
                if len(parts) < 2:
                    ui.print_warning("Usage: /provider use <name> [model]")
                else:
                    pname = parts[1]
                    target_model = parts[2] if len(parts) > 2 else None
                    cfg = provider_mgr.switch_to_provider(pname, model=target_model, config_mgr=self.config_mgr)
                    if cfg:
                        self.agent.config = cfg
                        ui.print_success(f"Switched active provider to [bold cyan]{pname}[/bold cyan] (Model: [bold white]{cfg.model}[/bold white], Base URL: {cfg.base_url})")
                    else:
                        ui.print_error(f"Provider '{pname}' not found. Run /provider list to view providers.")

        elif cmd in ("/window", "/pane", "/win"):
            from cord.ui.multipane import multipane_mgr
            parts = arg.strip().split()
            sub = parts[0].lower() if parts else "status"

            if sub in ("split", "v", "vertical"):
                orientation = "v"
                m_name = None
                if len(parts) > 1 and parts[1].lower() in ("h", "horizontal", "s", "horizontal_split"):
                    orientation = "h"
                    m_name = parts[2] if len(parts) > 2 else None
                elif len(parts) > 1 and parts[1].lower() in ("v", "vertical"):
                    orientation = "v"
                    m_name = parts[2] if len(parts) > 2 else None
                else:
                    m_name = parts[1] if len(parts) > 1 else None

                if orientation == "h":
                    pane = multipane_mgr.split_horizontal(model=m_name)
                else:
                    pane = multipane_mgr.split_vertical(model=m_name)

                ui.print_success(f"Opened new window [bold cyan]#{pane.id}[/bold cyan] ({'Vertical' if orientation == 'v' else 'Horizontal'} Split, Model: {pane.model})")
                ui.console.print(multipane_mgr.render_multipane_layout())

            elif sub in ("switch", "next", "focus"):
                target_id = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
                p = multipane_mgr.switch_pane(target_id)
                ui.print_success(f"Focused Window [bold cyan]#{p.id}[/bold cyan] ({p.model})")
                ui.console.print(multipane_mgr.render_multipane_layout())

            elif sub in ("close", "kill", "q"):
                target_id = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
                closed = multipane_mgr.close_pane(target_id)
                if closed:
                    ui.print_success(f"Closed window. Active window is now [bold cyan]#{multipane_mgr.active_id}[/bold cyan]")
                else:
                    ui.print_warning("Cannot close primary window. At least 1 window must remain.")

            elif sub in ("resize", "size"):
                delta = 0.05
                if len(parts) > 1:
                    raw_val = parts[1]
                    if raw_val.startswith("+"):
                        delta = float(raw_val[1:]) / 100.0 if raw_val[1:].isdigit() else 0.05
                    elif raw_val.startswith("-"):
                        delta = -float(raw_val[1:]) / 100.0 if raw_val[1:].isdigit() else -0.05
                    elif raw_val.isdigit():
                        multipane_mgr.split_ratio = max(0.15, min(0.85, float(raw_val) / 100.0))
                        delta = 0.0
                new_ratio = multipane_mgr.resize_split(delta)
                ui.print_success(f"Resized window split ratio to [bold cyan]{int(new_ratio * 100)}% / {int((1-new_ratio)*100)}%[/bold cyan]")
                ui.console.print(multipane_mgr.render_multipane_layout())

            else:
                ui.console.print(multipane_mgr.render_multipane_layout())
                ui.console.print(f"[dim]Multiplexer: {len(multipane_mgr.panes)} window(s) | Split: {multipane_mgr.split_type} | Ratio: {int(multipane_mgr.split_ratio*100)}%[/dim]")
                ui.console.print("[dim]Commands: /window split [v|h] [model] │ /window switch │ /window resize [+N|-N] │ /window close[/dim]")
                ui.console.print("[dim]Shortcuts: Ctrl+W v (split vertical) │ Ctrl+W s (split horizontal) │ Ctrl+W w (switch) │ Ctrl+W +/- (resize)[/dim]\n")

        elif cmd == "/theme":
            self._change_theme(arg)

        elif cmd == "/plan":
            if plan_mgr.current_plan:
                plan_mgr.render()
            else:
                ui.print_info("No active plan. Ask CORD to create a plan for your task!")

        elif cmd in ("/subagents", "/agents", "/agent", "/subagent", "/peers", "/peer", "/monitor"):
            from cord.ui.subagent_viewer import show_subagent_dashboard, open_subagent_monitor
            if arg.strip() and self.subagents:
                target = self.subagents.get_agent(arg.strip())
                if target:
                    await open_subagent_monitor(self, target)
                else:
                    await show_subagent_dashboard(self)
            else:
                await show_subagent_dashboard(self)

        elif cmd == "/mcp":
            self._print_mcp()

        elif cmd in ("/skills", "/skill"):
            self._print_skills(arg.strip())

        elif cmd == "/cost":
            self._print_cost()

        elif cmd == "/diff":
            from cord.ui.changes_dashboard import render_changes_dashboard
            render_changes_dashboard()

        elif cmd in ("/split", "/sidebar"):
            from cord.ui.split_view import sidebar_state, render_sidebar_panel
            is_open = sidebar_state.toggle()
            panel = render_sidebar_panel(
                tokens=self.agent.total_input_tokens + self.agent.total_output_tokens,
                input_tokens=self.agent.total_input_tokens,
                output_tokens=self.agent.total_output_tokens,
                model=self.config_mgr.config.model,
                mcp_mgr=self.mcp,
                workspace_dir=self.config_mgr.config.workspace_dir,
            )
            ui.console.print(panel)
            if is_open:
                ui.print_success("Split sidebar ENABLED! Use /split or Ctrl+S to toggle.")
            else:
                ui.print_info("Split sidebar toggled off.")

        elif cmd in ("/swarm", "/mesh"):
            from cord.ui.subagent_viewer import show_subagent_dashboard
            await show_subagent_dashboard(self)

        elif cmd in ("/msg", "/send"):
            parts = arg.strip().split(" ", 1)
            if len(parts) >= 2:
                from cord.subagents.message_bus import swarm_bus
                swarm_bus.send(sender_id="main", recipient_id=parts[0], content=parts[1])
                ui.print_success(f"✔ Message delivered to peer '{parts[0]}' from Main Agent.")
            else:
                ui.print_warning("Usage: /msg <peer_id> <message>")

        elif cmd == "/broadcast":
            if arg.strip():
                from cord.subagents.message_bus import swarm_bus
                swarm_bus.broadcast(sender_id="main", content=arg.strip())
                ui.print_success(f"✔ Broadcast published across swarm mesh ({swarm_bus.agent_count:,} virtual peers).")
            else:
                ui.print_warning("Usage: /broadcast <message>")


        elif cmd == "/yolo":
            self.config_mgr.update(permission_mode="yolo")
            self.agent.config.permission_mode = "yolo"
            ui.print_success("Switched permission mode to [bold green]YOLO[/bold green] (Autonomous).")

        elif cmd == "/strict":
            self.config_mgr.update(permission_mode="strict")
            self.agent.config.permission_mode = "strict"
            ui.print_success("Switched permission mode to [bold red]STRICT[/bold red] (Ask for all).")

        elif cmd == "/balanced":
            self.config_mgr.update(permission_mode="balanced")
            self.agent.config.permission_mode = "balanced"
            ui.print_success("Switched permission mode to [bold yellow]BALANCED[/bold yellow].")

        elif cmd == "/mode":
            if arg:
                profile = mode_manager.set_mode(arg)
                if profile:
                    self.config_mgr.update(active_mode=profile.id.value)
                    self.agent.config.active_mode = profile.id.value
                    ui.print_success(
                        f"Switched to Mode: [{profile.badge_style}]{profile.badge} {profile.name}[/{profile.badge_style}]\n"
                        f"[dim]{profile.description}[/dim]"
                    )
                else:
                    ui.print_error(f"Unknown mode '{arg}'. Available: fast, computer, coder, agent")
            else:
                self._print_modes()

        elif cmd == "/sessions":
            self._handle_sessions_command(arg)

        elif cmd == "/resume":
            target = arg.strip()
            if not target:
                self._print_sessions()
                target = Prompt.ask("[bold cyan]Enter session ID or keyword to resume[/bold cyan]")
            if target:
                # Save existing session if it has messages
                if self.agent.messages:
                    session_manager.save_session(
                        messages=self.agent.messages,
                        model=self.config_mgr.config.model,
                        mode=mode_manager.current_mode.value,
                    )
                self.agent.reset()
                data = session_manager.load_session(target)
                if data:
                    self.agent.messages = data.get("messages", [])
                    self._rerender_full_session_history(data)
                else:
                    ui.print_error(f"Session '{target}' not found in ~/.cord/sessions/")

        elif cmd == "/new":
            session_manager.save_session(
                messages=self.agent.messages,
                model=self.config_mgr.config.model,
                mode=mode_manager.current_mode.value,
            )
            self.agent.reset()
            new_id = session_manager.get_new_session_id()
            ui.print_success(f"Started fresh session '{new_id}'. Previous session archived safely.")

        elif cmd == "/stats":
            render_stats_dashboard(
                workspace_path=Path(self.config_mgr.config.workspace_dir),
                session_start_time=self.agent.session_start_time,
                total_input_tokens=self.agent.total_input_tokens,
                total_output_tokens=self.agent.total_output_tokens,
                total_turns=len([m for m in self.agent.messages if m.get("role") == "user"])
            )

        elif cmd == "/models":
            self._print_saved_models()

        elif cmd == "/model":
            if arg:
                clean_arg = arg.strip()
                saved = self.config_mgr.config.saved_models.get(clean_arg)
                if saved:
                    update_kwargs = {
                        "model": saved["model"],
                        "provider": saved.get("provider", "custom"),
                        "base_url": saved.get("base_url", self.config_mgr.config.base_url),
                    }
                    if "api_key" in saved and saved["api_key"]:
                        update_kwargs["api_key"] = saved["api_key"]
                        self.agent.config.api_key = saved["api_key"]
                    self.config_mgr.update(**update_kwargs)
                    self.agent.config.model = saved["model"]
                    self.agent.config.provider = saved.get("provider", "custom")
                    self.agent.config.base_url = saved.get("base_url", self.config_mgr.config.base_url)
                    ui.print_success(f"Switched to saved model preset '[bold cyan]{clean_arg}[/bold cyan]': {saved['model']}")
                elif clean_arg.startswith("save "):
                    parts = clean_arg.split()
                    if len(parts) >= 3:
                        alias, mod_name = parts[1], parts[2]
                        self.config_mgr.config.saved_models[alias] = {
                            "model": mod_name,
                            "provider": self.config_mgr.config.provider,
                            "base_url": self.config_mgr.config.base_url,
                            "name": alias,
                        }
                        self.config_mgr.save_config()
                        ui.print_success(f"Saved model alias '[bold cyan]{alias}[/bold cyan]' -> {mod_name}")
                    else:
                        ui.print_info("Usage: /model save <alias> <model_name>")
                else:
                    self.config_mgr.update(model=clean_arg)
                    self.agent.config.model = clean_arg
                    ui.print_success(f"Model changed to: [bold cyan]{clean_arg}[/bold cyan]")
            else:
                self._print_saved_models()

        elif cmd == "/goal":
            goal_text = arg.strip()
            if not goal_text:
                goal_text = Prompt.ask("[bold green]Enter autonomous goal[/bold green]")
            if goal_text:
                runtime = AgentRuntime(self.config_mgr.config, self.agent.tools)
                await runtime.run_goal(goal_text)

        elif cmd == "/tasks":
            ui.console.print()
            ui.console.print(task_manager.render_tree())
            ui.console.print()

        elif cmd == "/tools":
            self._print_tools()

        elif cmd == "/doctor":
            run_doctor()

        elif cmd == "/stop":
            computer_safety.trigger_emergency_stop()
            ui.print_error("🚨 EMERGENCY KILL SWITCH ACTIVATED! All computer use and tool executions halted.")

        elif cmd == "/computer":
            sub = arg.strip().lower()
            if sub in ("off", "read_only", "interaction", "full_control"):
                computer_safety.safety_level = ComputerSafetyLevel(sub.upper())
                ui.print_success(f"Computer Use safety level set to: [bold cyan]{computer_safety.safety_level.value}[/bold cyan]")
            elif sub == "reset":
                computer_safety.reset_emergency_stop()
                ui.print_success("Emergency Kill Switch reset. Computer Use is now unblocked.")
            else:
                stopped_str = "[bold red]ACTIVE (HALTED)[/bold red]" if computer_safety.is_stopped() else "[bold green]INACTIVE[/bold green]"
                ui.console.print(f"\n[bold bright_white]🖥️ Computer Use Status:[/bold bright_white]")
                ui.console.print(f"  - Safety Level: [bold cyan]{computer_safety.safety_level.value}[/bold cyan]")
                ui.console.print(f"  - Kill Switch: {stopped_str}")
                ui.console.print(f"  - Screen Resolution: {computer_safety.screen_size[0]}x{computer_safety.screen_size[1]}")
                ui.console.print(f"  [dim]Usage: /computer <off|read_only|interaction|full_control|reset>[/dim]\n")

        elif cmd == "/hide":
            window_manager.hide_terminal()
            ui.print_info("Terminal window hidden. CORD is running silently in stealth mode.")

        elif cmd == "/show":
            window_manager.show_terminal()
            ui.print_info("Terminal window restored to foreground.")

        elif cmd in ("/copy", "/clipboard"):
            from cord.utils.clipboard import copy_to_clipboard
            clean_arg = arg.strip().lower()
            last_resp = ""
            for m in reversed(self.agent.messages):
                if m.get("role") == "assistant" and m.get("content"):
                    last_resp = m["content"]
                    break

            if not last_resp:
                ui.print_warning("No assistant response in memory to copy.")
            elif clean_arg == "code":
                code_blocks = re.findall(r"```(?:\w+)?\n([\s\S]*?)```", last_resp)
                if code_blocks:
                    joined = "\n\n".join(code_blocks)
                    if copy_to_clipboard(joined):
                        ui.print_success("📋 Code block(s) successfully copied to clipboard!")
                    else:
                        ui.print_error("Failed to copy code to clipboard.")
                else:
                    ui.print_warning("No code blocks found in the last response.")
            elif clean_arg == "all":
                all_text = []
                for m in self.agent.messages:
                    role = m.get("role", "unknown").upper()
                    cnt = m.get("content", "")
                    if cnt:
                        all_text.append(f"[{role}]:\n{cnt}\n")
                if copy_to_clipboard("\n".join(all_text)):
                    ui.print_success("📋 Full conversation transcript copied to clipboard!")
                else:
                    ui.print_error("Failed to copy transcript to clipboard.")
            else:
                if copy_to_clipboard(last_resp):
                    ui.print_success("📋 Last response copied to clipboard! (You can also select words with your mouse and right-click to copy).")
                else:
                    ui.print_error("Failed to copy to clipboard.")

        elif cmd in ("/mouse", "/mouse-mode"):
            clean_arg = arg.strip().lower()
            if clean_arg in ("pane", "interactive", "capture"):
                self.session.mouse_support = True
                ui.print_success("Mouse Mode: [bold cyan]Interactive Pane Capture[/bold cyan] (Allows window divider clicks).")
            elif clean_arg in ("native", "off", "scroll", "select", ""):
                self.session.mouse_support = False
                try:
                    sys.stdout.write("\x1b[?1000l\x1b[?1002l\x1b[?1003l\x1b[?1006l\x1b[?1049l\x1b[?1007l")
                    sys.stdout.flush()
                except Exception:
                    pass
                ui.print_success("Mouse Mode: [bold green]Native Selection & Scroll[/bold green] (Select words by dragging, right-click to copy, mouse wheel scrolls up/down).")
            else:
                ui.print_info("Usage: /mouse [native|pane] (default: native for word selection, copy, and scrolling)")

        elif cmd == "/live":
            live_sess = LiveVoiceSession(self.agent, self.config_mgr.config)
            await live_sess.run()

        elif cmd == "/mic":
            ui.print_info("Starting microphone recording... Speak now.")
            started = audio_recorder.start()
            if not started:
                err_msg = audio_recorder.last_error or "Failed to access audio recording device."
                ui.print_error(err_msg)
            else:
                Prompt.ask("[bold green]🎙️ Recording in progress... Press Enter to stop and transcribe[/bold green]")
                wav_file = audio_recorder.stop()
                if wav_file:
                    ui.print_info("Transcribing speech...")
                    transcribed = stt.transcribe(wav_file, self.config_mgr.config)
                    if transcribed and not transcribed.startswith("["):
                        ui.console.print(f"[bold cyan]🗣️ Transcribed:[/bold cyan] {transcribed}")
                        ui.console.print()
                        await self.agent.step(transcribed)
                        ui.console.print()
                    else:
                        ui.print_warning(f"Speech transcription result: {transcribed}")
                else:
                    ui.print_warning("No audio captured.")

        elif cmd == "/tts":
            sub = arg.strip()
            if sub.lower() in ("off", "disable", "stop"):
                tts.enabled = False
                tts.stop()
                ui.print_success("Text-To-Speech disabled.")
            elif sub.lower() in ("on", "enable"):
                tts.enabled = True
                ui.print_success("Text-To-Speech enabled.")
            elif sub:
                tts.speak(sub)
                ui.print_info(f"Speaking: '{sub}'")
            else:
                st = "Enabled" if tts.enabled else "Disabled"
                ui.print_info(f"TTS Status: {st}. Usage: /tts <text> or /tts <on|off>")

        else:
            ui.print_warning(f"Unknown command: '{cmd}'. Type '/help' for available commands.")

        return None

    def _print_help(self) -> None:
        table = Table(title="📖 CORD Slash Commands", show_header=True, header_style="bold cyan")
        table.add_column("Command", style="bold white", width=16)
        table.add_column("Description", style="dim")
        table.add_row("/menu", "Open interactive quick action dashboard (modes, models, languages, settings)")
        table.add_row("/mode", "Switch operational mode: fast (السريع), computer (مساعد), coder (مبرمج), agent (وكيل)")
        table.add_row("/sessions", "Interactive conversation browser & file-scoped chats (or press Ctrl+H)")
        table.add_row("/session file", "Scope current conversation to a target file (e.g. /session file app.py)")
        table.add_row("/changes", "Show complete visual dashboard of file diffs and session changelog")
        table.add_row("/inspect", "Interactive tool inspector: navigate tool calls with ↑/↓ arrow keys")
        table.add_row("/resume <id>", "Resume/restore a previous conversation session from history")
        table.add_row("/new", "Start a fresh session while safely archiving current conversation")
        table.add_row("/stats", "Show real-time codebase statistics, file counts, LOC, and session analytics")
        table.add_row("/models", "List saved model bookmarks and switch models (/model <alias>)")
        table.add_row("/scout", "Model Scout: Discover cutting-edge 2025/2026 models across Claude, Gemini, DeepSeek, Kimi")
        table.add_row("/update-models", "Register all newly discovered frontier models into ~/.cord/config.json")
        table.add_row("/goal", "Run fully autonomous closed-loop agent on a goal (/goal <desc>)")
        table.add_row("/tasks", "View live hierarchical task tree and state machine status")
        table.add_row("/tools", "List all 48+ registered native tools and schemas")
        table.add_row("/computer", "Inspect or set Computer Use safety level (OFF/READ_ONLY/INTERACTION/FULL_CONTROL)")
        table.add_row("/stop", "Emergency Kill Switch to instantly halt all computer use and executions")
        table.add_row("/doctor", "Run system diagnostics, environment, provider, and tool health check")
        table.add_row("/about", "Show animated system specifications, features & GitHub repository")
        table.add_row("/help", "Display this help reference")
        table.add_row("/settings", "Open interactive settings editor (API Key, Base URL, Model, Theme)")
        table.add_row("/undo", "Revert the last file modification made by the agent")
        table.add_row("/export", "Export the current session transcript to a Markdown file")
        table.add_row("/compact", "Compact conversation context to free up token window")
        table.add_row("/session", "Display session stats, memory usage, and checkpoints")
        table.add_row("/providers", "List all supported modern AI providers and top models")
        table.add_row("/theme", "Switch TUI theme (cyberpunk, monokai, dracula, nord)")
        table.add_row("/plan", "View current step-by-step implementation plan")
        table.add_row("/subagents", "View available subagent roles and recent executions")
        table.add_row("/mcp", "List connected MCP servers and available tools")
        table.add_row("/skills", "List discovered project skills")
        table.add_row("/cost", "Show token consumption and session usage statistics")
        table.add_row("/diff", "View recent git changes in the workspace")
        table.add_row("/yolo", "Quickly set permission mode to YOLO (Auto-approve non-destructive)")
        table.add_row("/balanced", "Quickly set permission mode to BALANCED (Default)")
        table.add_row("/strict", "Quickly set permission mode to STRICT (Ask permission for everything)")
        table.add_row("/clear", "Clear terminal screen and reset conversation history")
        table.add_row("/exit", "Exit CORD CLI")

        ui.console.print(table)

    def _print_tools(self) -> None:
        table = Table(title=f"🛠️ CORD Native Tool Suite ({len(self.agent.tools.tools)} Tools Registered)", show_header=True, header_style="bold cyan")
        table.add_column("Category", style="bold bright_white", width=14)
        table.add_column("Tool Name", style="cyan", width=22)
        table.add_column("Perm / Risk", style="dim", width=18)
        table.add_column("Description", style="white")

        categories = {
            "filesystem": ["list_directory", "read_file", "write_file", "edit_file", "move_file", "copy_file", "delete_file", "create_directory", "search_files"],
            "shell": ["execute_command", "run_shell"],
            "process": ["start_process", "stop_process", "get_processes"],
            "system": ["get_system_info", "get_cpu_usage", "get_memory_usage", "get_disk_usage", "get_environment"],
            "network": ["http_request", "download_file", "inspect_url", "fetch_web_page"],
            "git": ["git_status", "git_diff", "git_log", "git_branch", "git_checkout", "git_commit", "git_merge"],
            "developer": ["run_tests", "run_formatter", "run_linter", "install_dependencies"],
            "project": ["inspect_project", "detect_language", "detect_package_manager", "detect_framework", "run_project", "build_project"],
            "computer": ["computer_screenshot", "computer_mouse", "computer_keyboard", "computer_window", "windows_app", "browser_media"],
            "agent": ["spawn_subagent", "create_custom_subagent", "ask_user", "create_plan", "update_plan_step"],
        }

        for cat, tnames in categories.items():
            first = True
            for tname in tnames:
                t = self.agent.tools.get(tname)
                if t:
                    perm = getattr(t, "required_permission", "READ_ONLY")
                    perm_str = perm.value if hasattr(perm, "value") else str(perm)
                    risk = getattr(t, "risk_level", "LOW")
                    risk_str = risk.value if hasattr(risk, "value") else str(risk)
                    table.add_row(
                        cat.upper() if first else "",
                        t.name,
                        f"{perm_str} / {risk_str}",
                        t.description[:65] + ("..." if len(t.description) > 65 else "")
                    )
                    first = False

        ui.console.print(table)


    def _export_session(self) -> None:
        if not self.agent.messages:
            ui.print_info("No conversation messages to export.")
            return

        ts = time.strftime("%Y%m%d_%H%M%S")
        export_file = Path(self.config_mgr.config.workspace_dir) / f"cord_session_{ts}.md"

        lines = [
            f"# CORD Session Export — {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Model**: `{self.config_mgr.config.model}` | **Provider**: `{self.config_mgr.config.provider}`",
            f"**Total Tokens**: `{self.agent.total_input_tokens + self.agent.total_output_tokens:,}`\n",
            "---",
        ]

        for msg in self.agent.messages:
            role = msg.get("role", "unknown").upper()
            content = msg.get("content", "")
            lines.append(f"\n### {role}\n")
            lines.append(content)
            if "tool_calls" in msg:
                lines.append(f"\n*Tool Calls*: `{len(msg['tool_calls'])} calls*")

        try:
            export_file.write_text("\n".join(lines), encoding="utf-8")
            ui.print_success(f"Session transcript exported to: [bold cyan]{export_file.name}[/bold cyan]")
        except Exception as e:
            ui.print_error(f"Failed to export session: {e}")

    def _print_session_info(self) -> None:
        elapsed_sec = int(time.time() - self.agent.session_start_time)
        m, s = divmod(elapsed_sec, 60)
        h, m = divmod(m, 60)

        table = Table(title="📊 CORD Session Intelligence", show_header=True, header_style="bold cyan")
        table.add_column("Property", style="bold white", width=22)
        table.add_column("Value", style="bold green")

        table.add_row("Session Uptime", f"{h:02d}h {m:02d}m {s:02d}s")
        table.add_row("Messages in Memory", str(len(self.agent.messages)))
        table.add_row("File Checkpoints", str(len(checkpoint_mgr.history)))
        table.add_row("Input Tokens", f"{self.agent.total_input_tokens:,}")
        table.add_row("Output Tokens", f"{self.agent.total_output_tokens:,}")
        table.add_row("Registered Tools", str(len(self.agent.tools.tools)))
        table.add_row("Active Theme", self.config_mgr.config.theme)

        ui.console.print(table)

    def _print_providers(self) -> None:
        table = Table(title="🌐 Supported Modern AI Providers & Models", show_header=True, header_style="bold cyan")
        table.add_column("Provider", style="bold white", width=18)
        table.add_column("Default Model", style="bold green", width=28)
        table.add_column("Top Models", style="dim")

        for key, p in PROVIDER_PRESETS.items():
            top = ", ".join(p["models"][:3])
            table.add_row(p["name"], p["default_model"], top)

        ui.console.print(table)

    def _change_theme(self, theme_name: str) -> None:
        available = list(THEMES.keys())
        if not theme_name or theme_name not in available:
            console = ui.console
            theme_name = Prompt.ask("Select theme", choices=available, default=self.config_mgr.config.theme)

        self.config_mgr.update(theme=theme_name)
        ui.set_theme(theme_name)
        ui.print_success(f"Theme switched to: [bold magenta]{theme_name}[/bold magenta]")

    def _print_subagents(self) -> None:
        if not self.subagents:
            ui.print_info("Subagents engine is disabled.")
            return

        eff_cfg = self.subagents.get_effective_config()
        ui.console.print(
            f"\n[bold magenta]🤖 CORD Subagents Engine & Mesh[/bold magenta]\n"
            f"[dim]Inherited Provider:[/dim] [bold cyan]{eff_cfg.provider}[/bold cyan] │ "
            f"[dim]Inherited Model:[/dim] [bold cyan]{eff_cfg.model}[/bold cyan] │ "
            f"[dim]Parent Spawner:[/dim] [green]Active Agent Session[/green]\n"
        )

        roles = self.subagents.get_available_roles()
        table = Table(title="Available Subagent Roles", show_header=True, header_style="bold magenta")
        table.add_column("Role", style="bold white", width=16)
        table.add_column("Description", style="dim")

        for r, desc in roles.items():
            table.add_row(r.upper(), desc)

        ui.console.print(table)

        if self.subagents.history:
            hist_table = Table(title="Recent Subagent Executions", show_header=True, header_style="bold cyan")
            hist_table.add_column("Role", style="bold white", width=14)
            hist_table.add_column("Provider / Model", style="dim cyan", width=26)
            hist_table.add_column("Status", justify="center", width=10)
            hist_table.add_column("Tools", justify="center", width=8)
            hist_table.add_column("Summary", style="white")

            for res in self.subagents.history[-8:]:
                st = "[bold green]Success ✓[/bold green]" if res.success else "[bold red]Failed ✖[/bold red]"
                hist_table.add_row(
                    res.role.upper(),
                    f"{res.provider or eff_cfg.provider} / {res.model or eff_cfg.model}",
                    st,
                    str(res.tool_calls_count),
                    res.summary[:80] + ("..." if len(res.summary) > 80 else ""),
                )
            ui.console.print(hist_table)

    def _print_mcp(self) -> None:
        if not self.mcp or not self.mcp.tools:
            ui.print_info("No MCP servers currently active. Configure servers in ~/.cord/mcp.json.")
            return

        table = Table(title="🔌 Connected MCP Tools", show_header=True, header_style="bold green")
        table.add_column("Tool Name", style="bold white", width=25)
        table.add_column("Server", style="bold cyan", width=15)
        table.add_column("Description", style="dim")

        for t in self.mcp.get_tools():
            srv = getattr(t, "server_name", "mcp")
            table.add_row(t.name, srv, t.description[:60])

        ui.console.print(table)

    def _print_skills(self, arg: str = "") -> None:
        if not self.skills:
            ui.print_info("Skills engine is not initialized.")
            return

        parts = arg.split(maxsplit=1) if arg else []
        subcmd = parts[0].lower() if parts else "list"
        subarg = parts[1].strip() if len(parts) > 1 else ""

        if subcmd in ("reload", "refresh"):
            self.skills.reload()
            ui.print_success(f"✨ Skills reloaded! Active skills count: [bold cyan]{len(self.skills.skills)}[/bold cyan]")
            return

        if subcmd in ("info", "show", "view"):
            if not subarg:
                ui.print_warning("Usage: /skills info <skill-name>")
                return
            target = self.skills.get_skill(subarg)
            if not target:
                ui.print_error(f"Skill '{subarg}' not found. Run /skills to see available skills.")
                return
            is_builtin = "builtin" in str(target.path).lower()
            badge = "[bold green]Built-in System Skill[/bold green]" if is_builtin else "[bold magenta]Workspace Skill[/bold magenta]"
            panel_content = (
                f"[bold cyan]Category:[/bold cyan] {target.category}   •   [bold cyan]Type:[/bold cyan] {badge}\n"
                f"[bold cyan]Location:[/bold cyan] [dim]{target.path}[/dim]\n"
                f"[bold cyan]Description:[/bold cyan] {target.description}\n\n"
                f"[bold yellow]Instructions Injected into System Prompt:[/bold yellow]\n"
                f"[white]{target.instructions}[/white]"
            )
            ui.console.print(Panel(panel_content, title=f"✨ Skill: [bold white]{target.name}[/bold white]", border_style="cyan", padding=(1, 2)))
            return

        if subcmd in ("new", "create"):
            if not subarg:
                ui.print_warning("Usage: /skills new <skill-name>")
                return
            created_path = self.skills.create_skill(
                name=subarg,
                description=f"Specialized instructions for {subarg}",
                instructions=f"Guidelines and directives for executing {subarg} tasks effectively.",
                category="Custom",
            )
            ui.print_success(f"✔ Created new skill template at: [bold cyan]{created_path}[/bold cyan]")
            ui.print_info("You can customize its directives anytime by editing the file.")
            return

        # Default: list all skills
        all_skills = self.skills.list_skills() if hasattr(self.skills, "list_skills") else list(self.skills.skills.values())
        if not all_skills:
            ui.print_info("No skills currently loaded.")
            return

        table = Table(
            title=f"✨ CORD Specialized Skills Library ({len(all_skills)} Active)",
            show_header=True,
            header_style="bold cyan",
            border_style="bright_blue",
        )
        table.add_column("Category", style="yellow", width=18)
        table.add_column("Skill Name", style="bold white", width=22)
        table.add_column("Type", justify="center", width=12)
        table.add_column("Description", style="dim")

        for s in all_skills:
            is_builtin = "builtin" in str(s.path).lower()
            type_pill = "[bold green]Built-in[/bold green]" if is_builtin else "[bold magenta]Custom[/bold magenta]"
            cat = getattr(s, "category", "General")
            table.add_row(f"🏷️  {cat}", f"`{s.name}`", type_pill, s.description[:70] + ("..." if len(s.description) > 70 else ""))

        ui.console.print(table)
        ui.console.print("[dim]Commands: [cyan]/skills info <name>[/cyan] (view prompt) │ [cyan]/skills new <name>[/cyan] (create) │ [cyan]/skills reload[/cyan][/dim]\n")

    def _print_cost(self) -> None:
        from cord.ui.split_view import calculate_real_cost
        in_tok = self.agent.total_input_tokens
        out_tok = self.agent.total_output_tokens
        total = in_tok + out_tok
        model = self.config_mgr.config.model
        real_cost = calculate_real_cost(model, in_tok, out_tok)

        table = Table(title="📊 Real Session Token Usage & Spend", show_header=True, header_style="bold cyan")
        table.add_column("Metric", style="bold white", width=22)
        table.add_column("Value", style="bold green", width=26)

        table.add_row("Active Model", model)
        table.add_row("Input Tokens", f"{in_tok:,}")
        table.add_row("Output Tokens", f"{out_tok:,}")
        table.add_row("Total Tokens", f"{total:,}")
        table.add_row("Real Estimated Spend", f"${real_cost:.4f} USD")

        ui.console.print(table)

    async def _show_diff(self) -> None:
        from cord.tools.shell_tools import RunShellTool
        tool = RunShellTool()
        res = await tool.execute(command="git status --short; git diff")
        if res.success and res.output.strip():
            ui.console.print(Panel(res.output, title="Git Diff / Status", border_style="cyan"))
        else:
            ui.print_info("No uncommitted git changes found, or git is not installed.")

    def _print_modes(self) -> None:
        table = Table(title="🎯 CORD 4 Operational Modes", show_header=True, header_style="bold cyan")
        table.add_column("Mode Key", style="bold white", width=14)
        table.add_column("Badge", width=16)
        table.add_column("Name", style="cyan", width=18)
        table.add_column("Role & Description", style="dim")

        cur = mode_manager.current_mode
        for m, prof in MODE_PROFILES.items():
            active_marker = " [bold green]◄ ACTIVE[/bold green]" if m == cur else ""
            table.add_row(
                f"{m.value}{active_marker}",
                f"[{prof.badge_style}]{prof.badge}[/{prof.badge_style}]",
                prof.name,
                prof.description
            )
        ui.console.print(table)
        ui.console.print("[dim]Switch mode: /mode <fast|computer|coder|agent>[/dim]\n")

    def _handle_sessions_command(self, arg: str = "") -> None:
        target_file = None
        clean_arg = arg.strip()
        if clean_arg.startswith("file "):
            target_file = str(Path(clean_arg[5:].strip()).expanduser().resolve())

        sessions = session_manager.list_sessions(target_file=target_file)
        if not sessions:
            scope_str = f" for {Path(target_file).name}" if target_file else ""
            ui.print_info(f"No saved sessions found in ~/.cord/sessions/{scope_str}.")
            return

        table = Table(title="💾 Saved Conversation Sessions & File Scopes", show_header=True, header_style="bold cyan")
        table.add_column("#", style="bold yellow", width=4)
        table.add_column("Session ID", style="bold cyan", width=22)
        table.add_column("Scope / File", style="bold magenta", width=18)
        table.add_column("Title / First Prompt", style="white", width=30)
        table.add_column("Mode", style="yellow", width=8)
        table.add_column("Msgs", justify="center", width=6)
        table.add_column("Changes", justify="center", width=10)
        table.add_column("Updated", style="dim", width=16)

        for idx, s in enumerate(sessions[:15], start=1):
            dt = time.strftime("%Y-%m-%d %H:%M", time.localtime(s["updated_at"]))
            tfile = s.get("target_file")
            scope_badge = f"[📁 {Path(tfile).name}]" if tfile else "[🌐 Global]"
            
            tot_add = s.get("lines_added", 0)
            tot_rem = s.get("lines_removed", 0)
            diff_badge = f"[green]+{tot_add}[/green] [red]-{tot_rem}[/red]" if (tot_add or tot_rem) else "[dim]none[/dim]"

            table.add_row(
                str(idx),
                s["id"],
                scope_badge,
                s["title"][:28] + ("..." if len(s["title"]) > 28 else ""),
                s.get("mode", "agent"),
                str(s["message_count"]),
                diff_badge,
                dt
            )
        ui.console.print(table)
        ui.console.print("[dim]Select a session [#] or ID to resume (or press Enter to return)[/dim]")
        try:
            choice = Prompt.ask("[bold cyan]Resume session #[/bold cyan]", default="")
            if choice.strip():
                sel_id = choice.strip()
                if sel_id.isdigit() and 1 <= int(sel_id) <= len(sessions):
                    sel_id = sessions[int(sel_id) - 1]["id"]
                if self.agent.messages:
                    session_manager.save_session(
                        messages=self.agent.messages,
                        model=self.config_mgr.config.model,
                        mode=mode_manager.current_mode.value,
                    )
                self.agent.reset()
                data = session_manager.load_session(sel_id)
                if data:
                    self.agent.messages = data.get("messages", [])
                    self._rerender_full_session_history(data)
                else:
                    ui.print_error(f"Session '{sel_id}' not found.")
        except Exception:
            pass

    def _rerender_full_session_history(self, data: Dict[str, Any]) -> None:
        """Clears console and completely re-renders the visual chat history, cards, thoughts, and diffs of the restored session."""
        ui.console.clear()

        sid = data.get("session_id", "unknown")
        title = data.get("title", "Untitled Session")
        model = data.get("model", self.config_mgr.config.model)
        mode_val = data.get("mode", "agent").upper()
        target_file = data.get("target_file")
        file_badge = f"📁 [bold cyan]{target_file}[/bold cyan]" if target_file else "🌐 [dim]Workspace Wide[/dim]"
        msgs = data.get("messages", [])

        # 1. Print visual resumed session banner
        ui.console.print(Panel(
            f"[bold #38bdf8]CORD Conversation Session Restored & Isolated[/bold #38bdf8]\n"
            f"[bold white]ID:[/bold white] [green]{sid}[/green]  │  "
            f"[bold white]Mode:[/bold white] [magenta]{mode_val}[/magenta]  │  "
            f"[bold white]Model:[/bold white] [yellow]{model}[/yellow]  │  "
            f"{file_badge}\n"
            f"[dim italic]\"{title}\"[/dim italic]",
            border_style="cyan",
            title="[bold green]✔ Session Loaded[/bold green]",
            expand=False,
        ))
        ui.console.print()

        # 2. Re-render UI events if present
        ui_events = data.get("ui_events", [])
        if ui_events:
            for evt in ui_events:
                etype = evt.get("type")
                if etype == "user_query":
                    renderer.render_user_message(evt.get("text", ""))
                elif etype == "thinking":
                    ui.console.print(f"\n[bold #a855f7]╭─ 💭 Thought Process ─╮[/bold #a855f7]")
                    ui.console.print(f"[dim italic #d8b4fe]{evt.get('text', '')}[/dim italic #d8b4fe]")
                    ui.console.print("[bold #a855f7]╰" + "─" * 40 + "╯[/bold #a855f7]\n")
                elif etype == "assistant_text":
                    renderer.render_assistant_header(evt.get("model", model))
                    from rich.markdown import Markdown
                    ui.console.print(Markdown(evt.get("text", "")))
                    ui.console.print()
                elif etype == "tool_call":
                    from cord.tools.base import ToolResult
                    res_obj = ToolResult(output=evt.get("output", ""), success=evt.get("success", True))
                    renderer.render_tool_execution(
                        evt.get("name", ""),
                        evt.get("args", {}),
                        res_obj,
                        evt.get("elapsed", 0.0)
                    )
        else:
            # Fallback reconstruction from raw messages
            for msg in msgs:
                role = msg.get("role")
                content = msg.get("content")
                if role == "user":
                    if isinstance(content, str):
                        renderer.render_user_message(content)
                elif role == "assistant":
                    renderer.render_assistant_header(model)
                    if isinstance(content, str) and content.strip():
                        from rich.markdown import Markdown
                        ui.console.print(Markdown(content))
                    for tc in msg.get("tool_calls", []):
                        fn = tc.get("function", {})
                        t_name = fn.get("name", "")
                        try:
                            t_args = json.loads(fn.get("arguments", "{}"))
                        except Exception:
                            t_args = {}
                        from cord.tools.base import ToolResult
                        res_obj = ToolResult(output="[Saved Tool Execution Output]", success=True)
                        renderer.render_tool_execution(t_name, t_args, res_obj, 0.0)
                ui.console.print()

        # 3. If session recorded file changes, show changelog badge
        changes = data.get("changes", [])
        if changes:
            ui.console.print(
                f"[dim cyan]📝 Recorded {len(changes)} file modifications in this session. "
                f"Use [bold]/changes[/bold] to inspect unified diffs.[/dim cyan]\n"
            )

        ui.print_success(
            f"Resumed session '{sid}': \"{title}\" "
            f"({len(msgs)} messages re-rendered)"
        )

    def _print_sessions(self) -> None:
        self._handle_sessions_command("")

    def _print_saved_models(self) -> None:
        saved = self.config_mgr.config.saved_models
        table = Table(title="🤖 Saved Model Bookmarks & Presets", show_header=True, header_style="bold cyan")
        table.add_column("Alias", style="bold cyan", width=16)
        table.add_column("Model ID", style="white", width=34)
        table.add_column("Provider", style="magenta", width=14)
        table.add_column("Preset Name", style="dim")

        cur_model = self.config_mgr.config.model
        for alias, info in saved.items():
            is_cur = " [bold green]◄ CURRENT[/bold green]" if info["model"] == cur_model else ""
            table.add_row(
                f"{alias}{is_cur}",
                info["model"],
                info.get("provider", "custom"),
                info.get("name", alias)
            )
        ui.console.print(table)
        ui.console.print("[dim]Switch model: /model <alias_or_name> │ Bookmark current: /model save <alias> <model_id>[/dim]\n")

    def _print_languages(self) -> None:
        table = Table(title="🌐 Supported Interface Languages", show_header=True, header_style="bold cyan")
        table.add_column("Code", style="bold cyan", width=8)
        table.add_column("Flag", justify="center", width=6)
        table.add_column("Language", style="bold white", width=22)
        table.add_column("Direction", style="dim", width=12)

        cur_lang = getattr(self.config_mgr.config, "language", "ar")
        for code, info in LANGUAGES.items():
            is_cur = " [bold green]◄ CURRENT[/bold green]" if code == cur_lang else ""
            table.add_row(
                f"{code}{is_cur}",
                info["flag"],
                info["name"],
                info["dir"].upper()
            )
        ui.console.print(table)
        ui.console.print("[dim]Switch language: /lang <code> (e.g. /lang ar, /lang en, /lang fr, /lang tr)[/dim]\n")

