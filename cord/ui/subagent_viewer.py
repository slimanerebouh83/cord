"""
CORD UI - Interactive Subagent Swarm Dashboard & Live Observation Deck
Provides mouse-clickable terminal navigation, real-time activity and thought inspection,
swarm communication monitoring, and Main-Agent-mediated coordination.

Architecture:
1. Swarm Dashboard: Mouse-clickable table of peers + action buttons with keyboard shortcuts.
2. Observation Deck: Subagents are inspected in view-only mode; direct user conversation is
   strictly reserved for the Main Agent (المستخدم يتحدث مع الرئيسي فقط). All directives entered
   here are dispatched to the Main Agent to coordinate the swarm.
3. Swarm Mesh Equality: Main agent and all subagents are equal peers (كلهم سواسية) communicating
   over the shared swarm message bus.
"""

from __future__ import annotations
import sys
import time
import inspect
import json
from typing import Any, Optional, List, Dict

from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.prompt import Prompt

from cord.ui.console import ui
from cord.subagents.base_subagent import Subagent, SubagentResult
from cord.subagents.message_bus import swarm_bus
from cord.subagents.roles import ROLE_CONFIGS


def _make_clickable_link(text: str, uri: str) -> str:
    """Renders an OSC 8 terminal hyperlink if supported by the user's terminal."""
    return f"\033]8;;{uri}\033\\{text}\033]8;;\033\\"


ROLE_ICONS = {
    "coder": "💻",
    "researcher": "🔍",
    "reviewer": "🛡️",
    "tester": "🧪",
    "custom": "⚙️",
    "general": "🤖",
    "architect": "📐",
    "debugger": "🐞",
}


def _get_role_icon(role: str) -> str:
    clean = (role or "").lower()
    for k, icon in ROLE_ICONS.items():
        if k in clean:
            return icon
    return "🤖"


def _is_interactive_console() -> bool:
    """Detects whether standard output is connected to a genuine interactive Windows/UNIX console buffer."""
    try:
        if not sys.stdout.isatty():
            return False
        if sys.platform == "win32":
            from prompt_toolkit.output.win32 import Win32Output
            out = Win32Output(sys.stdout)
            out.get_win32_screen_buffer_info()
        return True
    except Exception:
        return False


async def show_subagent_dashboard(repl: Any) -> None:
    """
    Renders an interactive Subagent Swarm Dashboard.
    Supports native mouse clicks on subagent rows and buttons in interactive terminals,
    with keyboard shortcuts (1-9, n, b, r, 0/q) and graceful fallback to Rich prompts.
    """
    if not hasattr(repl, "subagents") or not repl.subagents:
        ui.print_warning("Subagent engine is not initialized in this session.")
        return

    mgr = repl.subagents

    while True:
        active_agents = mgr.list_agents()

        # In interactive console, run prompt_toolkit mouse-clickable application
        if _is_interactive_console():
            try:
                choice = await _run_interactive_mouse_dashboard(repl, mgr, active_agents)
            except Exception:
                choice = await _run_rich_terminal_dashboard(repl, mgr, active_agents)
        else:
            choice = await _run_rich_terminal_dashboard(repl, mgr, active_agents)

        if not choice or choice in ("0", "q", "exit", "quit", "back", "select:main", "action:quit"):
            ui.console.print("[dim]Returning to Main Agent chat...[/dim]\n")
            break

        if choice in ("n", "new", "create", "spawn", "action:spawn"):
            await _spawn_subagent_interactively(repl)
            continue

        if choice in ("b", "broadcast", "action:broadcast"):
            msg = Prompt.ask("[bold magenta]Enter message to broadcast to all swarm peers[/bold magenta]").strip()
            if msg:
                swarm_bus.broadcast(sender_id="main", content=msg)
                ui.print_success(f"✔ Broadcast message published across swarm mesh ({swarm_bus.agent_count:,} virtual peers).")
            continue

        if choice in ("r", "refresh", "action:refresh"):
            continue

        # Handle agent selection: either "select:<name>" or raw number/name
        target_name = choice[7:] if choice.startswith("select:") else choice
        target_agent = mgr.get_agent(target_name)
        if not target_agent:
            # Try numeric index lookup
            try:
                idx = int(target_name)
                if 1 <= idx <= len(active_agents):
                    target_agent = active_agents[idx - 1]
            except ValueError:
                pass

        if target_agent:
            await open_subagent_monitor(repl, target_agent)
        else:
            ui.print_warning(f"Unknown subagent '{target_name}'. Please select a valid peer.")


async def _run_interactive_mouse_dashboard(repl: Any, mgr: Any, active_agents: List[Subagent]) -> str:
    """
    Renders a mouse-clickable and keyboard-navigable dashboard using prompt_toolkit.
    Clicking any subagent row or action button with the mouse immediately triggers that selection.
    """
    from prompt_toolkit.application import Application
    from prompt_toolkit.layout.containers import HSplit, Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.layout.layout import Layout
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.mouse_events import MouseEvent, MouseEventType, MouseButton
    from prompt_toolkit.styles import Style

    eff_cfg = mgr.get_effective_config()
    main_msgs = len(repl.agent.messages) if hasattr(repl, "agent") and repl.agent else 0
    main_tools = len(repl.agent.tool_history) if hasattr(repl, "agent") and repl.agent else 0

    kb = KeyBindings()
    fragments: List[Any] = []

    def make_click_handler(res_val: str):
        def _on_click(mouse_event: MouseEvent):
            if mouse_event.event_type in (MouseEventType.MOUSE_UP, MouseEventType.MOUSE_DOWN):
                from prompt_toolkit.application.current import get_app
                app = get_app()
                app.exit(result=res_val)
        return _on_click

    # Keybindings
    @kb.add("0")
    @kb.add("q")
    @kb.add("escape")
    def _(event):
        event.app.exit(result="action:quit")

    @kb.add("n")
    def _(event):
        event.app.exit(result="action:spawn")

    @kb.add("b")
    def _(event):
        event.app.exit(result="action:broadcast")

    @kb.add("r")
    def _(event):
        event.app.exit(result="action:refresh")

    for i in range(1, 10):
        def _make_num_kb(idx: int):
            def _num_handler(event):
                if idx <= len(active_agents):
                    event.app.exit(result=f"select:{active_agents[idx - 1].name}")
            return _num_handler
        kb.add(str(i))(_make_num_kb(i))

    # Build UI Fragments
    fragments.append(("class:header", "╔═════════════════════════════════════════════════════════════════════════════════════════════════════════════════════╗\n"))
    fragments.append(("class:header", "║ 🤖 CORD Autonomous Subagents & Peer Swarm Mesh │ كلهم سواسية                                                       ║\n"))
    fragments.append(("class:header", f"║ Model: {eff_cfg.model:<30} Provider: {eff_cfg.provider:<12} Active Peers: {len(active_agents) + 1:<4} Swarm Bus: Connected ║\n"))
    fragments.append(("class:header", "║ 🖱️  MOUSE & KEYBOARD: Click on any subagent row or button below to inspect!                                         ║\n"))
    fragments.append(("class:header", "╠═════╦══════════════════════╦════════════════╦════════════╦═════════════════════════════╦══════╦══════╦═════════════════╣\n"))
    fragments.append(("class:tbl_head", "║  #  ║ Peer / Agent ID      ║ Role           ║ Status     ║ Model / Provider            ║ Msgs ║ Tool ║ Summary         ║\n"))
    fragments.append(("class:header", "╠═════╬══════════════════════╬════════════════╬════════════╬═════════════════════════════╬══════╬══════╬═════════════════╣\n"))

    # Row 0: Main Agent
    main_summary = "Central interactive coding peer & coordinator"[:35]
    main_line = f"║  0  ║ ⭐ main (Main Agent)  ║ 🧠 Orchestrator║ ● Active   ║ {eff_cfg.model[:16]:<16} ({eff_cfg.provider[:8]:<8}) ║ {main_msgs:<4} ║ {main_tools:<4} ║ {main_summary:<15} ║\n"
    fragments.append(("class:row_main", main_line, make_click_handler("select:main")))

    # Subagent Rows
    for idx, ag in enumerate(active_agents, start=1):
        icon = _get_role_icon(ag.role)
        name_str = f"{icon} {ag.name}"[:20]
        role_str = ag.role.capitalize()[:14]
        st_str = "⚡ Running" if ag.status == "running" else ("✔ Complete" if ag.status == "completed" else "● Idle")
        model_str = f"{ag.config.model[:16]} ({ag.config.provider[:8]})"
        m_cnt = len(ag.messages)
        t_cnt = getattr(ag, "total_tool_calls", len(getattr(ag, "tool_history", [])))
        summ = (getattr(ag, "summary", "") or "(Ready)")[:15]

        row_str = f"║ {idx:<3} ║ {name_str:<20} ║ {role_str:<14} ║ {st_str:<10} ║ {model_str:<27} ║ {m_cnt:<4} ║ {t_cnt:<4} ║ {summ:<15} ║\n"
        row_style = "class:row_even" if idx % 2 == 0 else "class:row_odd"
        fragments.append((row_style, row_str, make_click_handler(f"select:{ag.name}")))

    fragments.append(("class:header", "╚═════╩══════════════════════╩════════════════╩════════════╩═════════════════════════════╩══════╩══════╩═════════════════╝\n\n"))

    # Clickable Action Buttons Bar
    fragments.append(("class:btn_main", " [ ⭐ 0. Main Agent ] ", make_click_handler("select:main")))
    fragments.append(("class:space", "  "))
    fragments.append(("class:btn_spawn", " [ ➕ n. Spawn Subagent ] ", make_click_handler("action:spawn")))
    fragments.append(("class:space", "  "))
    fragments.append(("class:btn_bcast", " [ 📢 b. Swarm Broadcast ] ", make_click_handler("action:broadcast")))
    fragments.append(("class:space", "  "))
    fragments.append(("class:btn_refresh", " [ 🔄 r. Refresh ] ", make_click_handler("action:refresh")))
    fragments.append(("class:space", "  "))
    fragments.append(("class:btn_exit", " [ ❌ q. Exit Dashboard ] \n\n", make_click_handler("action:quit")))

    fragments.append(("class:hint", "💡 Tip: Click with your mouse on any agent row to enter its Observation Deck, or press 1-9 on your keyboard.\n"))

    style = Style.from_dict({
        "header": "fg:#38bdf8 bold",
        "tbl_head": "fg:#60a5fa bold",
        "row_main": "fg:#ffffff bg:#1e293b bold",
        "row_even": "fg:#e2e8f0 bg:#0f172a",
        "row_odd": "fg:#f8fafc bg:#1e1e38",
        "btn_main": "fg:#ffffff bg:#2563eb bold",
        "btn_spawn": "fg:#ffffff bg:#059669 bold",
        "btn_bcast": "fg:#ffffff bg:#7c3aed bold",
        "btn_refresh": "fg:#ffffff bg:#0284c7 bold",
        "btn_exit": "fg:#ffffff bg:#dc2626 bold",
        "hint": "fg:#94a3b8 italic",
        "space": "",
    })

    output = None
    try:
        from prompt_toolkit.output import create_output
        output = create_output()
    except Exception:
        from prompt_toolkit.output import DummyOutput
        output = DummyOutput()

    control = FormattedTextControl(fragments)
    app = Application(
        layout=Layout(HSplit([Window(content=control)])),
        key_bindings=kb,
        style=style,
        mouse_support=True,
        full_screen=False,
        output=output,
    )

    result = await app.run_async()
    return result or "action:quit"


async def _run_rich_terminal_dashboard(repl: Any, mgr: Any, active_agents: List[Subagent]) -> str:
    """
    Standard Rich table rendering fallback for non-console environments, automated tests, or redirected pipes.
    """
    eff_cfg = mgr.get_effective_config()
    table = Table(
        title="🤖 [bold #38bdf8]CORD Autonomous Subagents & Peer Swarm Mesh[/bold #38bdf8] │ [bold green]كلهم سواسية[/bold green]",
        show_header=True,
        header_style="bold #38bdf8",
        border_style="#2563eb",
        padding=(0, 1),
        expand=True,
    )
    table.add_column("#", style="bold yellow", justify="center", width=4)
    table.add_column("Peer / Agent ID", style="bold white", width=22)
    table.add_column("Role", style="cyan", width=14)
    table.add_column("Status", justify="center", width=12)
    table.add_column("Model / Provider", style="dim", width=28)
    table.add_column("Msgs", justify="center", width=6)
    table.add_column("Tools", justify="center", width=6)
    table.add_column("Latest Summary / Activity", style="white")

    # Peer #0: Main Agent
    main_msgs = len(repl.agent.messages) if hasattr(repl, "agent") and repl.agent else 0
    main_tools = len(repl.agent.tool_history) if hasattr(repl, "agent") and repl.agent else 0
    table.add_row(
        "[bold white]0[/bold white]",
        _make_clickable_link("⭐ main (Main Agent)", "subagent://main"),
        "🧠 Orchestrator",
        "[bold green]● Active[/bold green]",
        f"{eff_cfg.model} ({eff_cfg.provider})",
        str(main_msgs),
        str(main_tools),
        "[dim]Central interactive coding peer & swarm node[/dim]",
    )

    for idx, ag in enumerate(active_agents, start=1):
        status_style = {
            "running": "[bold yellow]⚡ Running[/bold yellow]",
            "completed": "[bold green]✔ Complete[/bold green]",
            "idle": "[dim]● Idle[/dim]",
            "error": "[bold red]✖ Error[/bold red]",
        }.get(getattr(ag, "status", "idle"), "[dim]● Ready[/dim]")

        icon = _get_role_icon(ag.role)
        clickable_name = _make_clickable_link(f"{icon} {ag.name}", f"subagent://{ag.name}")
        summary = getattr(ag, "summary", "") or "(Ready for task)"
        if len(summary) > 65:
            summary = summary[:62] + "..."

        msg_count = len(ag.messages)
        tool_count = getattr(ag, "total_tool_calls", len(getattr(ag, "tool_history", [])))

        table.add_row(
            f"[bold cyan]{idx}[/bold cyan]",
            clickable_name,
            ag.role.capitalize(),
            status_style,
            f"{ag.config.model} ({ag.config.provider})",
            str(msg_count),
            str(tool_count),
            summary,
        )

    ui.console.print("\n")
    ui.console.print(Panel(
        table,
        border_style="#2563eb",
        subtitle=f"[dim]Enter [bold cyan]1-{len(active_agents)}[/bold cyan] to inspect │ [bold yellow]n[/bold yellow]: New subagent │ [bold magenta]b[/bold magenta]: Broadcast │ [bold white]0/q[/bold white]: Main Agent[/dim]",
        subtitle_align="center",
    ))

    max_idx = len(active_agents)
    prompt_text = (
        f"[bold cyan]Select subagent to inspect [1-{max_idx}], 'n' to spawn, 'b' to broadcast, '0' or 'q' to return[/bold cyan]"
        if max_idx > 0
        else "[bold cyan]Enter 'n' to spawn a new subagent, 'b' to broadcast, '0' or 'q' to return[/bold cyan]"
    )

    try:
        choice = Prompt.ask(prompt_text, default="0").strip().lower()
    except (KeyboardInterrupt, EOFError):
        choice = "0"

    return choice


async def open_subagent_monitor(repl: Any, subagent: Subagent) -> None:
    """
    Subagent Live Observation & Inspection Deck (شاشة المراقبة والتحليل الحية).
    
    IMPORTANT USER ARCHITECTURE:
    "وعندما المستخدم يدخل الشات تبعه لا يمكنه التحدث معه المستخدم يتحدث مع الرئيسي فقط"
    The user DOES NOT chat directly with the subagent; the subagent view is view-only inspection.
    Any directive or prompt entered by the user is routed to the MAIN AGENT to coordinate and manage this subagent!
    """
    active_tab = 1  # 1: Activity, 2: Thoughts, 3: Tools, 4: Swarm Bus, 5: Specs

    while True:
        ui.console.clear()
        eff_cfg = subagent.config
        icon = _get_role_icon(subagent.role)

        # 1. Prominent Observation Deck Banner (Clarifying Main-Agent Routing)
        banner_text = (
            f"[bold #38bdf8]🔒 CORD SUBAGENT LIVE OBSERVATION DECK[/bold #38bdf8] │ [bold green]شاشة المراقبة والتحليل[/bold green]\n"
            f"[bold yellow]⚠️  تنبيه هام:[/bold yellow] [bold white]المحادثة المباشرة محصورة مع الوكيل الرئيسي فقط (المستخدم يتحدث مع الرئيسي فقط).[/bold white]\n"
            f"[dim]أي توجيه أو استفسار تدخله هنا يتم إرساله فوراً إلى الوكيل الرئيسي لتوجيه وإدارة هذا الوكيل الفرعي.[/dim]\n"
            f"[dim]Direct chatting is handled exclusively via the Main Agent. Any directive entered is forwarded to Main Agent.[/dim]"
        )
        ui.console.print(Panel(banner_text, border_style="#38bdf8", expand=True))

        # 2. Subagent Identity & Status Summary Card
        status_badge = {
            "running": "[bold yellow]⚡ RUNNING[/bold yellow]",
            "completed": "[bold green]✔ COMPLETED[/bold green]",
            "idle": "[dim green]● IDLE / READY[/dim green]",
            "error": "[bold red]✖ ERROR[/bold red]",
        }.get(getattr(subagent, "status", "idle"), "[dim]● READY[/dim]")

        thought_count = len(getattr(subagent, "thinking_history", []))
        tool_count = getattr(subagent, "total_tool_calls", len(getattr(subagent, "tool_history", [])))
        current_obj = getattr(subagent, "current_task", "") or getattr(subagent, "summary", "") or "(Awaiting task from Main Agent)"

        summary_card = (
            f"• [bold white]Peer:[/bold white] [bold cyan]{icon} {subagent.name}[/bold cyan]  │  "
            f"[bold white]Role:[/bold white] [bold yellow]{subagent.role.upper()}[/bold yellow]  │  "
            f"[bold white]Status:[/bold white] {status_badge}  │  "
            f"[bold white]Swarm Mesh:[/bold white] [bold green]Connected (كلهم سواسية)[/bold green]\n"
            f"• [bold white]Model:[/bold white] [cyan]{eff_cfg.model}[/cyan]  │  "
            f"[bold white]Provider:[/bold white] [cyan]{eff_cfg.provider}[/cyan]  │  "
            f"[bold white]Messages:[/bold white] {len(subagent.messages)}  │  "
            f"[bold white]Tool Calls:[/bold white] {tool_count}  │  "
            f"[bold white]Thoughts:[/bold white] {thought_count}\n"
            f"• [bold white]Current Objective:[/bold white] [italic white]{current_obj[:90]}[/italic white]"
        )
        ui.console.print(Panel(summary_card, border_style="#6366f1", title=f"[bold #818cf8]● INSPECT: {subagent.name.upper()}[/bold #818cf8]", expand=True))

        # 3. Interactive Tabs Navigation Bar
        def tab_btn(num: int, label: str) -> str:
            if active_tab == num:
                return f"[bold black on #38bdf8] ► [{num}. {label}] [/bold black on #38bdf8]"
            return f"[bold #94a3b8] [{num}. {label}] [/bold #94a3b8]"

        tabs_line = (
            f"{tab_btn(1, '📜 Activity Stream')}  "
            f"{tab_btn(2, '🧠 Thoughts & Reasoning')}  "
            f"{tab_btn(3, '🛠️ Tool Executions')}  "
            f"{tab_btn(4, '💬 Swarm Bus')}  "
            f"{tab_btn(5, '📊 Telemetry & Specs')}  "
            f"[bold red] [0. ⬅️ Return to Main Agent] [/bold red]"
        )
        ui.console.print(f"\n{tabs_line}\n")

        # 4. Tab Content Rendering
        if active_tab == 1:
            # TAB 1: ACTIVITY STREAM
            if not subagent.messages:
                ui.console.print(Panel("[dim]No activity recorded yet. The subagent is currently idle and awaiting tasks from Main Agent.[/dim]", title="📜 Activity Stream"))
            else:
                ui.console.print("[dim]─── Chronological Subagent Activity & Dialogue ───[/dim]")
                for m_idx, msg in enumerate(subagent.messages, start=1):
                    role = msg.get("role", "")
                    content = msg.get("content", "")
                    if role == "user":
                        ui.console.print(f"\n[bold #38bdf8]📥 Task / Directive #{m_idx} (From Main Agent):[/bold #38bdf8]\n{content}")
                    elif role == "assistant":
                        if content:
                            ui.console.print(f"\n[bold #a855f7]🤖 [{subagent.name}] Response #{m_idx}:[/bold #a855f7]\n{content}")
                        if "tool_calls" in msg:
                            tc_names = [tc.get("function", {}).get("name", "") for tc in msg["tool_calls"]]
                            ui.console.print(f"[dim #38bdf8]  ↳ Invoked {len(tc_names)} tool(s): {', '.join(tc_names)}[/dim #38bdf8]")
                    elif role == "tool":
                        t_name = msg.get("name", "tool")
                        preview = content[:150] + ("..." if len(content) > 150 else "")
                        ui.console.print(f"[dim]  ↳ Tool Result ({t_name}): {preview}[/dim]")
                ui.console.print("[dim]──────────────────────────────────────────────────[/dim]\n")

        elif active_tab == 2:
            # TAB 2: THOUGHTS & REASONING
            thoughts = getattr(subagent, "thinking_history", [])
            # Also extract thoughts from messages if any
            extra_thoughts = []
            for m in subagent.messages:
                c = m.get("content", "")
                if "<thought>" in c and "</thought>" in c:
                    part = c.split("<thought>", 1)[1].split("</thought>", 1)[0].strip()
                    if part and part not in thoughts:
                        extra_thoughts.append(part)

            all_thoughts = thoughts + extra_thoughts
            if not all_thoughts:
                ui.console.print(Panel("[dim]No internal thinking logs recorded yet. Reasoning will stream here live as the subagent thinks.[/dim]", title="🧠 Thoughts & Live Reasoning"))
            else:
                for idx, th in enumerate(all_thoughts, start=1):
                    ui.console.print(Panel(
                        f"[dim #c084fc]{th}[/dim #c084fc]",
                        title=f"[bold #a855f7]🧠 Thinking & Synthesis Step #{idx}[/bold #a855f7]",
                        border_style="#a855f7",
                    ))

        elif active_tab == 3:
            # TAB 3: TOOL EXECUTIONS
            history = getattr(subagent, "tool_history", [])
            # Also fallback to extracting from messages if history is empty
            if not history:
                extracted = []
                for m in subagent.messages:
                    if m.get("role") == "tool":
                        extracted.append({
                            "tool": m.get("name", "tool"),
                            "args": {},
                            "result": m.get("content", ""),
                            "success": "Error" not in m.get("content", ""),
                            "timestamp": time.time(),
                        })
                history = extracted

            if not history:
                ui.console.print(Panel("[dim]No tools executed by this subagent yet.[/dim]", title="🛠️ Tool Executions"))
            else:
                t_table = Table(title=f"🛠️ Tool Invocation History ({len(history)} calls)", border_style="#38bdf8", expand=True)
                t_table.add_column("#", style="bold yellow", width=4)
                t_table.add_column("Tool Name", style="bold cyan", width=22)
                t_table.add_column("Arguments", style="white", width=35)
                t_table.add_column("Result Snippet", style="dim")
                t_table.add_column("Status", justify="center", width=10)

                for idx, t_entry in enumerate(history, start=1):
                    t_name = t_entry.get("tool", "unknown")
                    t_args = json.dumps(t_entry.get("args", {}), ensure_ascii=False)[:35]
                    t_res = str(t_entry.get("result", ""))[:90].replace("\n", " ")
                    st = "[bold green]✔ OK[/bold green]" if t_entry.get("success", True) else "[bold red]✖ FAIL[/bold red]"
                    t_table.add_row(str(idx), t_name, t_args, t_res, st)
                ui.console.print(t_table)

        elif active_tab == 4:
            # TAB 4: SWARM BUS MESSAGES
            all_swarm = swarm_bus.get_inbox(subagent.name, unread_only=False)
            # Find broadcast messages or sent messages
            outbox = [m for m in getattr(swarm_bus, "_history", []) if getattr(m, "sender_id", "") == subagent.name]

            s_table = Table(title=f"💬 Swarm Mesh Inter-Peer Messages ({len(all_swarm) + len(outbox)} records)", border_style="#a855f7", expand=True)
            s_table.add_column("Dir", justify="center", width=6)
            s_table.add_column("Peer", style="bold cyan", width=18)
            s_table.add_column("Time", style="dim", width=12)
            s_table.add_column("Message Content", style="white")

            for m in all_swarm[-15:]:
                s_table.add_row("📥 IN", m.get("from", "peer"), m.get("time", "")[-8:], m.get("content", ""))
            for m in outbox[-10:]:
                t_str = time.strftime("%H:%M:%S", time.localtime(getattr(m, "timestamp", time.time())))
                s_table.add_row("📤 OUT", getattr(m, "recipient_id", "mesh"), t_str, getattr(m, "content", ""))

            if not all_swarm and not outbox:
                ui.console.print(Panel(
                    "[dim]No peer messages exchanged on the Swarm Bus yet.\n"
                    "💡 Peer agents automatically share insights, plans, and results over this mesh (كلهم سواسية).[/dim]",
                    title="💬 Swarm Bus Mesh",
                ))
            else:
                ui.console.print(s_table)

        elif active_tab == 5:
            # TAB 5: TELEMETRY & SPECS
            spec_table = Table(title=f"📊 Subagent Specifications & Telemetry: [{subagent.name}]", border_style="#10b981", expand=True)
            spec_table.add_column("Property", style="bold cyan", width=25)
            spec_table.add_column("Value", style="bold white")

            spec_table.add_row("Identifier", subagent.name)
            spec_table.add_row("Specialized Role", subagent.role.capitalize())
            spec_table.add_row("Model", subagent.config.model)
            spec_table.add_row("Provider", subagent.config.provider)
            spec_table.add_row("Base URL", subagent.config.base_url or "(Default provider endpoint)")
            spec_table.add_row("Max Loop Iterations", str(subagent.max_iterations))
            spec_table.add_row("Parent Coordinator", getattr(subagent, "parent_name", "main"))
            spec_table.add_row("Registered Tools", ", ".join(list(subagent.tools.keys())[:12]) or "None")
            spec_table.add_row("Total Context Messages", str(len(subagent.messages)))
            spec_table.add_row("Lifetime Tool Calls", str(getattr(subagent, "total_tool_calls", 0)))
            uptime_sec = int(time.time() - getattr(subagent, "created_at", time.time()))
            spec_table.add_row("Uptime", f"{uptime_sec // 60}m {uptime_sec % 60}s")
            spec_table.add_row("Swarm Peer Equality", "Enabled (Main Agent & Subagents are equal peers - كلهم سواسية)")

            ui.console.print(spec_table)

        # 5. User Directive Input Prompt
        ui.console.print(
            f"\n[dim]Commands: [bold white]1-5[/bold white] (Switch Tab) │ [bold white]r[/bold white] (Refresh) │ "
            f"[bold white]0[/bold white] or [bold white]q[/bold white] (Return to Main Agent) │ "
            f"[bold cyan]Or enter any directive to forward to Main Agent[/bold cyan][/dim]"
        )

        try:
            prompt_label = f"[bold #38bdf8]│[/bold #38bdf8] [bold cyan]{subagent.name}[/bold cyan] [dim](Observation Deck)[/dim] ❯ "
            user_input = ui.console.input(prompt_label).strip()
        except (KeyboardInterrupt, EOFError):
            ui.console.print("\n[dim]Returning to Main Agent chat...[/dim]\n")
            break

        if not user_input:
            continue

        clean = user_input.strip()

        # Exit / Return to Main Agent
        if clean.lower() in ("0", "q", "/back", "/exit", "/quit", "/main", "back", "exit"):
            ui.console.print(f"[dim]Returning to Main Agent chat from [{subagent.name}]...[/dim]\n")
            break

        # Switch Tabs
        if clean in ("1", "2", "3", "4", "5"):
            active_tab = int(clean)
            continue
        if clean.lower() in ("/activity", "activity"):
            active_tab = 1
            continue
        if clean.lower() in ("/thoughts", "thoughts", "thinking"):
            active_tab = 2
            continue
        if clean.lower() in ("/tools", "tools"):
            active_tab = 3
            continue
        if clean.lower() in ("/swarm", "swarm", "bus", "/bus"):
            active_tab = 4
            continue
        if clean.lower() in ("/specs", "specs", "telemetry"):
            active_tab = 5
            continue

        # Refresh
        if clean.lower() in ("r", "/refresh", "refresh"):
            continue

        # Clear subagent history
        if clean.lower() == "/clear":
            subagent.reset_context()
            ui.print_success(f"Conversation and activity history for [{subagent.name}] cleared.")
            continue

        # Forward user directive to MAIN AGENT (المستخدم يتحدث مع الرئيسي فقط)
        ui.console.print(f"\n[bold #38bdf8]📤 Routing directive to Main Agent regarding [{subagent.name}]...[/bold #38bdf8]")
        ui.console.print(f"[dim]Main Agent is orchestrating and delegating: '{clean}'[/dim]\n")

        directive_prompt = f"[User Directive for Main Agent regarding subagent '{subagent.name}']: {clean}"
        if hasattr(repl, "agent") and repl.agent:
            await repl.agent.step(directive_prompt)
        else:
            ui.print_warning("Main Agent is not ready to receive directives.")

        # Re-display monitor with updated state after turn completes
        time.sleep(0.5)


# Alias for backwards compatibility
open_dedicated_subagent_chat = open_subagent_monitor


async def _spawn_subagent_interactively(repl: Any) -> None:
    """Interactively spawns a new subagent and opens its observation deck."""
    mgr = repl.subagents
    roles = list(ROLE_CONFIGS.keys())
    role_choice = Prompt.ask(
        "[bold cyan]Select subagent role[/bold cyan]",
        choices=roles + ["custom"],
        default="coder",
    ).strip().lower()

    custom_name = Prompt.ask(
        "[bold cyan]Enter subagent name (optional, press Enter for auto)[/bold cyan]",
        default="",
    ).strip() or None

    initial_task = Prompt.ask(
        "[bold cyan]Enter initial task or instructions (press Enter to start idle)[/bold cyan]",
        default="",
    ).strip()

    if role_choice == "custom":
        role_title = Prompt.ask("[bold cyan]Enter role title (e.g. Database Architect)[/bold cyan]", default="Architect").strip()
        sys_prompt = Prompt.ask(
            "[bold cyan]Enter custom system prompt[/bold cyan]",
            default=f"You are an expert {role_title}. Analyze tasks rigorously and implement high quality code.",
        ).strip()
        ag_name = custom_name or f"custom-{int(time.time()) % 10000}"
        if initial_task:
            res = await mgr.spawn_custom(
                name=ag_name,
                role_title=role_title,
                system_prompt=sys_prompt,
                tool_names=["read_file", "write_file", "edit_file", "execute_command", "search_files", "list_directory"],
                task=initial_task,
            )
            created_agent = mgr.get_agent(ag_name)
        else:
            created_agent = mgr.create_interactive_agent(role="coder", custom_name=ag_name)
    else:
        if initial_task:
            res = await mgr.spawn(role=role_choice, task=initial_task, custom_name=custom_name)
            created_agent = mgr.get_agent(custom_name) if custom_name else (mgr.list_agents()[-1] if mgr.list_agents() else None)
        else:
            created_agent = mgr.create_interactive_agent(role=role_choice, custom_name=custom_name)

    if created_agent:
        ui.print_success(f"✔ Subagent [bold cyan]{created_agent.name}[/bold cyan] ({created_agent.role}) created successfully!")
        await open_subagent_monitor(repl, created_agent)
