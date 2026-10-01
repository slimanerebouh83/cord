"""
CORD UI - Next-Gen Terminal Chat Renderer
Delivers Claude Code / OpenCode CLI aesthetics with chat bubbles, tool execution cards,
streaming thinking accordions, and unified diff syntax highlighting.
"""

from __future__ import annotations
import time
from pathlib import Path
from typing import Dict, Any, Optional
from rich.panel import Panel
from rich.text import Text
from rich.syntax import Syntax
from rich.markdown import Markdown
from rich.table import Table

from cord.ui.console import ui
from cord.ui.arabic import fix_arabic
from cord.tools.base import ToolResult


class ChatRenderer:
    """Renders modern terminal chat components."""

    @staticmethod
    def render_user_message(content: str) -> None:
        """Renders the user query with a distinct stylish banner."""
        timestamp = time.strftime("%H:%M:%S")
        title = f"[bold white on #3b82f6] 👤 USER [/bold white on #3b82f6] [dim]({timestamp})[/dim]"
        
        display_content = fix_arabic(content)
        panel = Panel(
            Text(display_content, style="bold bright_white"),
            title=title,
            title_align="left",
            border_style="#3b82f6",
            padding=(0, 1),
        )
        ui.console.print(panel)

    @staticmethod
    def render_assistant_header(model_name: str) -> None:
        """Renders assistant header badge before streaming starts."""
        short_model = model_name.split("/")[-1]
        timestamp = time.strftime("%H:%M:%S")
        ui.console.print(
            f"\n[bold black on #a855f7] 🤖 CORD [/bold black on #a855f7] "
            f"[bold magenta]{short_model}[/bold magenta] [dim]({timestamp})[/dim]"
        )

    @staticmethod
    def render_thinking_block(thinking_text: str) -> None:
        """Renders a collapsible or styled thinking/reasoning block."""
        if not thinking_text.strip():
            return
        
        # Indent thinking lines softly
        lines = thinking_text.strip().splitlines()
        preview = lines[:15]
        body = "\n".join(preview)
        if len(lines) > 15:
            body += f"\n... [+{len(lines) - 15} lines of reasoning hidden]"

        panel = Panel(
            Text(body, style="italic dim #e9d5ff"),
            title="[bold magenta]🧠 Thought Process[/bold magenta]",
            title_align="left",
            border_style="#7c3aed",
            padding=(0, 1),
        )
        ui.console.print(panel)

    @staticmethod
    def render_tool_execution(
        tool_name: str,
        args: Dict[str, Any],
        result: ToolResult,
        elapsed_sec: float = 0.0,
        elapsed: Optional[float] = None,
    ) -> None:
        """Renders ultra-gorgeous, modern cyberpunk tool execution cards with rich telemetry."""
        if elapsed is not None:
            elapsed_sec = elapsed
        time_str = f"{elapsed_sec * 1000:.0f}ms" if elapsed_sec < 1 else f"{elapsed_sec:.2f}s"
        t_lower = tool_name.lower()
        success = result.success
        status_badge = f"[bold green]✓ SUCCESS {time_str}[/bold green]" if success else f"[bold red]✖ FAILED ({time_str})[/bold red]"

        # 1. Grep / Search Files
        if any(k in t_lower for k in ("grep", "search_files", "search_file", "find_in_files", "search")):
            query = str(args.get("query") or args.get("pattern") or args.get("search_term") or "")
            if len(query) > 45:
                query = query[:42] + "..."
            match_count = 0
            if result.metadata and "matches" in result.metadata:
                match_count = len(result.metadata["matches"])
            elif result.output:
                lines = [l for l in result.output.splitlines() if l.strip()]
                match_count = len(lines)
            cnt_str = f"{match_count} matches"
            err_str = f" [bold red]✖ {result.error[:60]}[/bold red]" if not success and result.error else ""
            b_color = "#0ea5e9" if success else "#ef4444"

            card = (
                f" [bold {b_color}]╭─ [bold cyan]🔍 SEARCH & RECON[/bold cyan] [dim]•[/dim] [bold white]Grep[/bold white] \"[bright_white]{query}[/bright_white]\" "
                f"[dim]──[/dim] [{status_badge}] ─╮[/bold {b_color}]\n"
                f" [bold {b_color}]│[/bold {b_color}]  [bold white]Result:[/bold white] [bright_green]{cnt_str}[/bright_green] [dim]found in project codebase[/dim]{err_str}\n"
                f" [bold {b_color}]╰────────────────────────────────────────────────────────────────────────────╯[/bold {b_color}]"
            )
            ui.console.print(card)
            return

        # 2. Glob / List Directory / Find
        if any(k in t_lower for k in ("glob", "list_dir", "find_files", "find_by_name", "list_files", "list_directory")):
            pattern = str(args.get("pattern") or args.get("path") or args.get("directory_path") or args.get("dir") or "**/*")
            if len(pattern) > 45:
                pattern = pattern[:42] + "..."
            match_count = 0
            if result.metadata and "count" in result.metadata:
                match_count = result.metadata["count"]
            elif result.output:
                match_count = len([l for l in result.output.splitlines() if l.strip()])
            cnt_str = f"{match_count} matches"
            err_str = f" [bold red]✖ {result.error[:60]}[/bold red]" if not success and result.error else ""
            b_color = "#38bdf8" if success else "#ef4444"

            card = (
                f" [bold {b_color}]╭─ [bold cyan]📂 EXPLORER[/bold cyan] [dim]•[/dim] [bold white]Glob[/bold white] \"[bright_white]{pattern}[/bright_white]\" "
                f"[dim]──[/dim] [{status_badge}] ─╮[/bold {b_color}]\n"
                f" [bold {b_color}]│[/bold {b_color}]  [bold white]Matched:[/bold white] [bright_cyan]{cnt_str}[/bright_cyan] [dim]indexed across repository[/dim]{err_str}\n"
                f" [bold {b_color}]╰────────────────────────────────────────────────────────────────────────────╯[/bold {b_color}]"
            )
            ui.console.print(card)
            return

        # 3. Read File
        if any(k in t_lower for k in ("read_file", "view_file", "inspect_file")):
            raw_path = str(args.get("path") or args.get("file_path") or args.get("target_file") or args.get("absolutepath") or "")
            clean_path = raw_path.replace("\\", "/")
            short_path = clean_path
            if len(clean_path) > 55:
                parts = clean_path.split("/")
                short_path = ".../" + "/".join(parts[-3:])
            line_info = ""
            if "start_line" in args or "startline" in args:
                s = args.get("start_line", args.get("startline"))
                e = args.get("end_line", args.get("endline", ""))
                line_info = f" [dim](lines {s}-{e})[/dim]"
            err_str = f" [bold red]✖ {result.error[:60]}[/bold red]" if not success and result.error else ""
            b_color = "#10b981" if success else "#ef4444"

            card = (
                f" [bold {b_color}]╭─ [bold green]📄 FILE SYSTEM[/bold green] [dim]•[/dim] [bold white]Read[/bold white] [bright_white]{short_path}[/bright_white]{line_info} "
                f"[dim]──[/dim] [{status_badge}] ─╮[/bold {b_color}]\n"
                f" [bold {b_color}]│[/bold {b_color}]  [dim]Path:[/dim] [white]{clean_path}[/white]{err_str}\n"
                f" [bold {b_color}]╰────────────────────────────────────────────────────────────────────────────╯[/bold {b_color}]"
            )
            ui.console.print(card)
            return

        # 4. Edit / Write File
        if any(k in t_lower for k in ("edit_file", "write_file", "replace_file_content", "patch_file")):
            raw_path = str(args.get("path") or args.get("file_path") or args.get("target_file") or "")
            clean_path = raw_path.replace("\\", "/")
            short_path = clean_path
            if len(clean_path) > 50:
                parts = clean_path.split("/")
                short_path = ".../" + "/".join(parts[-3:])
            diff_str = ""
            added = 0
            removed = 0
            if result.metadata:
                added = result.metadata.get("lines_added", 0)
                removed = result.metadata.get("lines_removed", 0)
                diff_str = f" [bold green]+{added}[/bold green] [bold red]-{removed}[/bold red]"
            err_str = f" [bold red]✖ {result.error[:60]}[/bold red]" if not success and result.error else ""
            action_label = "Edit" if "edit" in t_lower or "replace" in t_lower else "Write"
            b_color = "#10b981" if success else "#ef4444"

            desc = str(args.get("description", ""))
            desc_line = f"\n [bold {b_color}]│[/bold {b_color}]  [dim]Change:[/dim] [bright_white]{desc[:70]}[/bright_white]" if desc else ""

            card = (
                f" [bold {b_color}]╭─ [bold green]✏️ SURGICAL WRITE[/bold green] [dim]•[/dim] [bold white]{action_label}[/bold white] [bright_white]{short_path}[/bright_white]{diff_str} "
                f"[dim]──[/dim] [{status_badge}] ─╮[/bold {b_color}]\n"
                f" [bold {b_color}]│[/bold {b_color}]  [dim]Target File:[/dim] [white]{clean_path}[/white] │ [bold green]+{added}[/bold green] added │ [bold red]-{removed}[/bold red] removed{err_str}{desc_line}\n"
                f" [bold {b_color}]╰────────────────────────────────────────────────────────────────────────────╯[/bold {b_color}]"
            )
            ui.console.print(card)
            return

        # 5. Shell / Command Execution
        if any(k in t_lower for k in ("execute_command", "run_command", "shell", "bash", "powershell")):
            cmd = str(args.get("command") or args.get("commandline") or "")
            cmd_preview = cmd if len(cmd) <= 60 else cmd[:57] + "..."
            status_str = f"[dim]({time_str})[/dim]" if success else "[bold red]failed[/bold red]"
            b_color = "#f59e0b" if success else "#ef4444"

            # Output preview
            out_preview = ""
            if result.output:
                first_lines = [l.strip() for l in result.output.splitlines() if l.strip()][:2]
                if first_lines:
                    out_preview = f"\n [bold {b_color}]│[/bold {b_color}]  [dim]Output:[/dim] [white]" + " │ ".join(first_lines)[:70] + "[/white]"
            elif result.error:
                out_preview = f"\n [bold {b_color}]│[/bold {b_color}]  [bold red]Error:[/bold red] [white]{result.error[:70]}[/white]"

            card = (
                f" [bold {b_color}]╭─ [bold yellow]⚡ TERMINAL EXECUTION[/bold yellow] [dim]•[/dim] [bold white]Command[/bold white] \"[bright_white]{cmd_preview}[/bright_white]\" {status_str} "
                f"[dim]──[/dim] [{status_badge}] ─╮[/bold {b_color}]\n"
                f" [bold {b_color}]│[/bold {b_color}]  [dim]$[/dim] [bright_yellow]{cmd_preview}[/bright_yellow]{out_preview}\n"
                f" [bold {b_color}]╰────────────────────────────────────────────────────────────────────────────╯[/bold {b_color}]"
            )
            ui.console.print(card)
            return

        # 6. NITEE & Computer Use
        if "nitee" in t_lower or "computer" in t_lower:
            action = str(args.get("action") or "")
            target = ""
            if "plan" in args and isinstance(args["plan"], list):
                target = f"[{len(args['plan'])} steps]"
            elif "element_id" in args:
                target = str(args["element_id"])
            elif "x" in args and "y" in args:
                target = f"({args.get('x')}, {args.get('y')})"
            elif "app_name" in args:
                target = str(args.get("app_name"))

            b_color = "#6366f1" if success else "#ef4444"
            out_str = (result.output or result.error or "")[:70]

            card = (
                f" [bold {b_color}]╭─ [bold #818cf8]🖥️ DESKTOP AUTOMATION[/bold #818cf8] [dim]•[/dim] [bold white]NITEE[/bold white] [bright_white]{action} {target}[/bright_white] "
                f"[dim]──[/dim] [{status_badge}] ─╮[/bold {b_color}]\n"
                f" [bold {b_color}]│[/bold {b_color}]  [bold white]Action:[/bold white] [bright_white]{action}[/bright_white] {target} │ [dim]{out_str}[/dim]\n"
                f" [bold {b_color}]╰────────────────────────────────────────────────────────────────────────────╯[/bold {b_color}]"
            )
            ui.console.print(card)
            return

        # 7. Agent & Swarm Dispatch
        if any(k in t_lower for k in ("agent", "swarm", "subagent")):
            name = str(args.get("role") or args.get("recipient") or args.get("name") or "Swarm Peer")
            b_color = "#a855f7" if success else "#ef4444"
            task = str(args.get("task") or args.get("instructions") or args.get("prompt") or "")
            task_line = f"\n [bold {b_color}]│[/bold {b_color}]  [dim]Assigned:[/dim] [bright_white]{task[:70]}[/bright_white]" if task else ""

            card = (
                f" [bold {b_color}]╭─ [bold magenta]🐝 SWARM PEER MESH[/bold magenta] [dim]•[/dim] [bold white]Agent[/bold white] [bright_white]{name}[/bright_white] "
                f"[dim]──[/dim] [{status_badge}] ─╮[/bold {b_color}]\n"
                f" [bold {b_color}]│[/bold {b_color}]  [bold white]Peer ID:[/bold white] [magenta]{name}[/magenta] [dim](Collaborative Autonomous Execution)[/dim]{task_line}\n"
                f" [bold {b_color}]╰────────────────────────────────────────────────────────────────────────────╯[/bold {b_color}]"
            )
            ui.console.print(card)
            return

        # 8. Dynamic Tool Creation & Self-Repair Factory
        if any(k in t_lower for k in ("create_dynamic_tool", "repair_dynamic_tool")):
            target_tool = str(args.get("name") or "dynamic_tool")
            is_repair = "repair" in t_lower
            action_type = "SELF-REPAIR & PATCH" if is_repair else "DYNAMIC SYNTHESIS"
            b_color = "#10b981" if success else "#ef4444"
            desc = str(args.get("description") or args.get("repair_instructions") or "")
            if len(desc) > 70:
                desc = desc[:67] + "..."
            card = (
                f" [bold {b_color}]╭─ [bold #ec4899]🧬 SELF-EVOLVING TOOL FACTORY[/bold #ec4899] [dim]•[/dim] [bold white]{action_type}[/bold white] [bright_cyan]'{target_tool}'[/bright_cyan] "
                f"[dim]──[/dim] [{status_badge}] ─╮[/bold {b_color}]\n"
                f" [bold {b_color}]│[/bold {b_color}]  [dim]Purpose:[/dim] [white]{desc}[/white]\n"
                f" [bold {b_color}]│[/bold {b_color}]  [dim]Engine:[/dim] [magenta]Dynamic AST Compilation[/magenta] │ [cyan]Live Verification[/cyan] │ [green]Swarm Registry Hot-Load[/green]\n"
                f" [bold {b_color}]╰────────────────────────────────────────────────────────────────────────────╯[/bold {b_color}]"
            )
            ui.console.print(card)
            return

        # General Fallback Card
        primary_arg = ""
        for k in ("path", "query", "action", "name", "text", "key", "url"):
            if k in args:
                primary_arg = str(args[k])
                break
        if not primary_arg and args:
            primary_arg = str(list(args.values())[0])
        if len(primary_arg) > 40:
            primary_arg = primary_arg[:37] + "..."

        b_color = "#38bdf8" if success else "#ef4444"
        out_summary = (result.output or result.error or "")[:75].replace("\n", " ")

        card = (
            f" [bold {b_color}]╭─ [bold cyan]⚙️ SYSTEM TOOL[/bold cyan] [dim]•[/dim] [bold white]{tool_name}[/bold white] \"[bright_white]{primary_arg}[/bright_white]\" "
            f"[dim]──[/dim] [{status_badge}] ─╮[/bold {b_color}]\n"
            f" [bold {b_color}]│[/bold {b_color}]  [dim]Result:[/dim] [white]{out_summary}[/white]\n"
            f" [bold {b_color}]╰────────────────────────────────────────────────────────────────────────────╯[/bold {b_color}]"
        )
        ui.console.print(card)

    @staticmethod
    def render_swarm_event(
        event_type: str,
        sender: str,
        recipient: str,
        summary: str,
    ) -> None:
        """Renders an elegant real-time notification when swarm subagents communicate or coordinate."""
        timestamp = time.strftime("%H:%M:%S")
        card = (
            f"\n [bold #a855f7]╭─ 🐝 SWARM COLLABORATION[/bold #a855f7] [dim]({timestamp})[/dim] "
            f"[dim]──────────────────────────────[/dim]\n"
            f" [bold #a855f7]│[/bold #a855f7]  [dim]Event:[/dim] [bold white]{event_type}[/bold white] "
            f"│ [dim]From:[/dim] [bold cyan]{sender}[/bold cyan] "
            f"→ [dim]To:[/dim] [bold magenta]{recipient}[/bold magenta]\n"
            f" [bold #a855f7]│[/bold #a855f7]  [bright_white]{summary}[/bright_white]\n"
            f" [bold #a855f7]╰────────────────────────────────────────────────────────────────────────────╯[/bold #a855f7]"
        )
        ui.console.print(card)

    @staticmethod
    def render_turn_telemetry(
        tokens: int,
        tok_per_sec: float,
        ttft_sec: float,
        model_name: str,
        failed_over: bool = False,
    ) -> None:
        """Renders live response speed, token count, and latency telemetry bar."""
        short_model = model_name.split("/")[-1]
        failover_badge = " [bold yellow](⚡ Auto-Failover)[/bold yellow]" if failed_over else ""
        
        telemetry_str = (
            f"[dim]⚡[/dim] [bold bright_green]{tokens}[/bold bright_green] [dim]tokens[/dim] "
            f"│ [bold cyan]{tok_per_sec:.1f}[/bold cyan] [dim]tok/s[/dim] "
            f"│ [dim]⏱️ TTFT:[/dim] [bold yellow]{ttft_sec:.2f}s[/bold yellow] "
            f"│ [dim]🤖[/dim] [bold magenta]{short_model}[/bold magenta]{failover_badge}"
        )
        ui.console.print(f"[dim]  └─[/dim] {telemetry_str}\n")

    @staticmethod
    def render_execution_summary(actions: list[dict[str, Any]], final_outcome: str = "") -> None:
        """Renders a comprehensive, modern plan summary of all completed actions and tools."""
        if not actions:
            return

        table = Table(
            title="📋 خطة العمل والمهام المنفذة (Execution Plan Summary)",
            title_style="bold cyan",
            border_style="#38bdf8",
            show_header=True,
            header_style="bold bright_white on #1e293b",
            expand=True,
        )
        table.add_column("#", style="dim", width=4, justify="center")
        table.add_column("الأداة / الإجراء (Tool/Action)", style="bold white", width=26)
        table.add_column("التفاصيل والهدف (Details)", style="bright_white", ratio=2)
        table.add_column("الحالة (Status)", style="bold", width=16, justify="center")

        for idx, act in enumerate(actions, start=1):
            t_name = str(act.get("tool", ""))
            details = str(act.get("details", ""))
            if len(details) > 80:
                details = details[:77] + "..."
            success = act.get("success", True)
            status = "[bold green]تم بنجاح ✓[/bold green]" if success else "[bold red]فشل ✖[/bold red]"
            table.add_row(str(idx), t_name, details, status)

        ui.console.print("\n", table)
        if final_outcome:
            clean_outcome = final_outcome.strip().splitlines()[-1] if "\n" in final_outcome.strip() else final_outcome.strip()
            if len(clean_outcome) > 120:
                clean_outcome = clean_outcome[:117] + "..."
            ui.console.print(f" [bold #38bdf8]🎯 النتيجة النهائية:[/bold #38bdf8] [bright_white]{clean_outcome}[/bright_white]\n")


renderer = ChatRenderer()
