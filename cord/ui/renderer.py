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
        elapsed_sec: float,
    ) -> None:
        """Renders ultra-compact one-line execution badge matching modern OpenCode style."""
        time_str = f"{elapsed_sec * 1000:.0f}ms" if elapsed_sec < 1 else f"{elapsed_sec:.1f}s"
        t_lower = tool_name.lower()

        # 1. Grep / Search Files
        if any(k in t_lower for k in ("grep", "search_files", "search_file", "find_in_files", "search")):
            query = str(args.get("query") or args.get("pattern") or args.get("search_term") or "")
            if len(query) > 40:
                query = query[:37] + "..."
            match_count = 0
            if result.metadata and "matches" in result.metadata:
                match_count = len(result.metadata["matches"])
            elif result.output:
                lines = [l for l in result.output.splitlines() if l.strip()]
                match_count = len(lines)
            cnt_str = f" [dim]({match_count} matches)[/dim]" if match_count > 0 else ""
            err_str = f" [bold red]✖ {result.error[:40]}[/bold red]" if not result.success and result.error else ""
            ui.console.print(f" [dim white]*[/dim white] [bold #38bdf8]Grep[/bold #38bdf8] \"[white]{query}[/white]\"{cnt_str}{err_str}")
            return

        # 2. Glob / List Directory / Find
        if any(k in t_lower for k in ("glob", "list_dir", "find_files", "find_by_name", "list_files", "list_directory")):
            pattern = str(args.get("pattern") or args.get("path") or args.get("directory_path") or args.get("dir") or "**/*")
            if len(pattern) > 40:
                pattern = pattern[:37] + "..."
            match_count = 0
            if result.metadata and "count" in result.metadata:
                match_count = result.metadata["count"]
            elif result.output:
                match_count = len([l for l in result.output.splitlines() if l.strip()])
            cnt_str = f" [dim]({match_count} matches)[/dim]" if match_count > 0 else ""
            err_str = f" [bold red]✖ {result.error[:40]}[/bold red]" if not result.success and result.error else ""
            ui.console.print(f" [dim white]*[/dim white] [bold #38bdf8]Glob[/bold #38bdf8] \"[white]{pattern}[/white]\"{cnt_str}{err_str}")
            return

        # 3. Read File
        if any(k in t_lower for k in ("read_file", "view_file", "inspect_file")):
            raw_path = str(args.get("path") or args.get("file_path") or args.get("target_file") or args.get("absolutepath") or "")
            clean_path = raw_path.replace("\\", "/")
            if len(clean_path) > 60:
                parts = clean_path.split("/")
                clean_path = ".../" + "/".join(parts[-3:])
            err_str = f" [bold red]✖ {result.error[:40]}[/bold red]" if not result.success and result.error else ""
            ui.console.print(f" [dim cyan]→[/dim cyan] [bold #38bdf8]Read[/bold #38bdf8] [white]{clean_path}[/white]{err_str}")
            return

        # 4. Edit / Write File
        if any(k in t_lower for k in ("edit_file", "write_file", "replace_file_content", "patch_file")):
            raw_path = str(args.get("path") or args.get("file_path") or args.get("target_file") or "")
            clean_path = raw_path.replace("\\", "/")
            if len(clean_path) > 50:
                parts = clean_path.split("/")
                clean_path = ".../" + "/".join(parts[-3:])
            diff_str = ""
            if result.metadata:
                added = result.metadata.get("lines_added", 0)
                removed = result.metadata.get("lines_removed", 0)
                if added or removed:
                    diff_str = f" [bold green]+{added}[/bold green] [bold red]-{removed}[/bold red]"
            err_str = f" [bold red]✖ {result.error[:40]}[/bold red]" if not result.success and result.error else ""
            action_label = "Edit" if "edit" in t_lower or "replace" in t_lower else "Write"
            ui.console.print(f" [bold green]✓[/bold green] [bold #38bdf8]{action_label}[/bold #38bdf8] [white]{clean_path}[/white]{diff_str}{err_str}")
            return

        # 5. Shell / Command Execution
        if any(k in t_lower for k in ("execute_command", "run_command", "shell", "bash")):
            cmd = str(args.get("command") or args.get("commandline") or "")
            if len(cmd) > 40:
                cmd = cmd[:37] + "..."
            status_str = f"[dim]({time_str})[/dim]" if result.success else "[bold red]failed[/bold red]"
            ui.console.print(f" [bold yellow]⚡[/bold yellow] [bold #38bdf8]Command[/bold #38bdf8] \"[white]{cmd}[/white]\" {status_str}")
            return

        # 6. NITEE & Computer Use
        if "nitee" in t_lower or "computer" in t_lower:
            action = str(args.get("action") or "")
            target = ""
            if "plan" in args and isinstance(args["plan"], list):
                target = f"[{len(args['plan'])} steps]"
            elif "element_id" in args:
                target = str(args["element_id"])
            ui.console.print(f" [bold #818cf8]🖥️[/bold #818cf8] [bold #38bdf8]NITEE[/bold #38bdf8] [white]{action} {target}[/white] [dim]({time_str})[/dim]")
            return

        # 7. Agent & Swarm Dispatch
        if any(k in t_lower for k in ("agent", "swarm", "subagent")):
            name = str(args.get("role") or args.get("recipient") or args.get("name") or "Swarm Worker")
            ui.console.print(f" [bold magenta]▣[/bold magenta] [bold #38bdf8]Agent[/bold #38bdf8] [white]{name}[/white] [dim]({time_str})[/dim]")
            return

        # General Fallback
        primary_arg = ""
        for k in ("path", "query", "action", "name", "text", "key"):
            if k in args:
                primary_arg = str(args[k])
                break
        if not primary_arg and args:
            primary_arg = str(list(args.values())[0])
        if len(primary_arg) > 35:
            primary_arg = primary_arg[:32] + "..."
        err_str = f" [bold red]✖ {result.error[:40]}[/bold red]" if not result.success and result.error else ""
        ui.console.print(f" [dim cyan]•[/dim cyan] [bold #38bdf8]{tool_name}[/bold #38bdf8] [white]{primary_arg}[/white] [dim]({time_str})[/dim]{err_str}")

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
