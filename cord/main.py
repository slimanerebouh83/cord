"""
CORD CLI - Main Application Entrypoint
Initializes configuration, launches the onboarding wizard if needed, and starts the agent/REPL.
Supports autonomous goals, CLI subcommands (doctor, tools, models, tasks), and full tool suite.
"""

from __future__ import annotations
import sys
import os
import argparse
import asyncio
from pathlib import Path

# Force UTF-8 on Windows terminal to prevent cp1256 / charmap encoding errors
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:
        pass
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stdin, "reconfigure"):
            sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from cord.core.config import ConfigManager, CordConfig
from cord.core.permissions import PermissionGuard
from cord.core.agent import CordAgent
from cord.core.agent_runtime import AgentRuntime
from cord.tools import get_default_tools
from cord.tools.registry import ToolRegistry
from cord.tools.subagent_tool import SpawnSubagentTool
from cord.tools.custom_subagent_tool import CreateCustomSubagentTool
from cord.tools.subagents import (
    CollaborativePlanTool,
    SubagentDeliberateTool,
    RunParallelSubagentsTool,
)
from cord.subagents.manager import SubagentManager
from cord.mcp.manager import MCPManager
from cord.skills.loader import SkillLoader
from cord.ui.console import ui
from cord.ui.onboarding import run_onboarding_wizard
from cord.ui.repl import CordREPL
from cord.cli.doctor import run_doctor
from cord.tasks.task_manager import task_manager
from cord.providers.provider_manager import provider_manager


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="cord",
        description="CORD — Autonomous Terminal Coding & Computer-Use Agent inspired by Claude Code and Codex.",
    )
    # Positional or subcommands
    parser.add_argument(
        "subcommand",
        nargs="?",
        choices=[
            "doctor", "tools", "tasks", "models", "setup", "agent",
            "serve-mcp", "mcp-server", "live", "fleet", "ssh", "cron",
            "daemon", "ollama", "voice", "graph", "impact", "sentinel", "radar", "about",
        ],
        help="CLI subcommand to execute (e.g. cord doctor, cord fleet, cord cron, cord ollama, cord voice, cord live)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Launch hands-free live voice agent mode.",
    )
    parser.add_argument(
        "extra_args",
        nargs="*",
        help="Arguments passed to subcommands (e.g. cord agent 'build full API')",
    )
    parser.add_argument(
        "-c", "--command",
        type=str,
        help="Execute a single command or prompt directly and exit.",
    )
    parser.add_argument(
        "-g", "--goal",
        type=str,
        help="Execute a fully autonomous closed-loop goal with verification and exit.",
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Run the interactive first-launch setup wizard.",
    )
    parser.add_argument(
        "-m", "--model",
        type=str,
        help="Override LLM model name for this session.",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        help="Override LLM API base URL.",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        help="Override API key.",
    )
    parser.add_argument(
        "--provider",
        type=str,
        help="Override LLM provider (openrouter, openai, anthropic, deepseek, ollama, groq, custom).",
    )
    parser.add_argument(
        "--yolo",
        action="store_true",
        help="Enable YOLO mode (auto-approve safe commands).",
    )
    parser.add_argument(
        "-f", "--file",
        type=str,
        help="Scope conversation session and changelog to a specific target file.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Enable STRICT mode (prompt for every tool).",
    )
    return parser.parse_args()


async def main_async() -> int:
    args = parse_args()

    # Fast subcommands that don't need full agent setup
    if args.subcommand == "doctor":
        run_doctor()
        return 0

    if args.subcommand in ("serve-mcp", "mcp-server"):
        from cord.mcp.server import MCPServer
        server = MCPServer()
        await server.run_stdio()
        return 0

    # Load configuration
    config_mgr = ConfigManager()

    # Check CLI overrides
    if args.model:
        config_mgr.config.model = args.model
    if args.base_url:
        config_mgr.config.base_url = args.base_url
    if args.api_key:
        config_mgr.config.api_key = args.api_key
    if args.provider:
        config_mgr.config.provider = args.provider
    if args.yolo:
        config_mgr.config.permission_mode = "yolo"
    elif args.strict:
        config_mgr.config.permission_mode = "strict"

    if args.file:
        from cord.memory.sessions import session_manager
        target_path = Path(args.file).expanduser().resolve()
        session_manager.set_target_file(str(target_path))
        ui.print_info(f"Target file scoped: [bold cyan]{target_path.name}[/bold cyan] ({target_path})")

    # If first run or unconfigured or user requested --setup / cord setup, launch onboarding wizard!
    if args.setup or args.subcommand == "setup" or not config_mgr.config.is_configured():
        run_onboarding_wizard(config_mgr)

    cfg = config_mgr.config
    ui.set_theme(cfg.theme)

    # 1. Initialize Permissions Guard
    permission_guard = PermissionGuard(cfg)

    # 2. Initialize Tool Registry and the complete standard tool suite (45 tools)
    tool_registry = ToolRegistry(permission_guard)
    tool_registry.register_many(get_default_tools())

    # Subcommand: cord tools
    if args.subcommand == "tools":
        from rich.table import Table
        table = Table(title=f"🛠️ CORD Registered Tools ({len(tool_registry.tools)} Tools)", border_style="cyan")
        table.add_column("Tool Name", style="bold cyan")
        table.add_column("Permission", style="yellow")
        table.add_column("Risk", style="magenta")
        table.add_column("Description", style="white")
        for t in tool_registry.tools.values():
            perm = getattr(t, "required_permission", "READ_ONLY")
            perm_s = perm.value if hasattr(perm, "value") else str(perm)
            risk = getattr(t, "risk_level", "LOW")
            risk_s = risk.value if hasattr(risk, "value") else str(risk)
            table.add_row(t.name, perm_s, risk_s, t.description[:70] + ("..." if len(t.description) > 70 else ""))
        ui.console.print(table)
        return 0

    # Subcommand: cord tasks
    if args.subcommand == "tasks":
        ui.console.print(task_manager.render_tree())
        return 0

    # Subcommand: cord models
    if args.subcommand == "models":
        from rich.table import Table
        table = Table(title="🤖 CORD Discovered AI Providers & Models", border_style="blue")
        table.add_column("Provider", style="bold cyan")
        table.add_column("Configured", justify="center")
        table.add_column("Masked Key / Source", style="dim")
        for p in provider_manager.discover_providers():
            table.add_row(
                p.name,
                "[bold green]✓ Yes[/bold green]" if p.is_configured else "[dim]No[/dim]",
                p.masked_key
            )
        ui.console.print(table)
        ui.console.print(f"Active Model: [bold bright_white]{cfg.model}[/bold bright_white] (Provider: [cyan]{cfg.provider}[/cyan])\n")
        return 0

    # Subcommand: cord fleet / cord ssh
    if args.subcommand in ("fleet", "ssh"):
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
            status_color = "bold green" if n.status == "online" else "yellow" if n.status == "configured" else "red"
            table.add_row(
                n.name,
                f"{n.user}@{n.host}:{n.port}",
                n.os_type,
                f"[{status_color}]{n.status}[/{status_color}]",
                ", ".join(n.tags) if n.tags else "-",
                n.description or "-",
            )
        ui.console.print(table)
        ui.console.print("[dim]Use 'cord' and prompt: 'add ssh node <name> <host>' or '/fleet' inside chat.[/dim]\n")
        return 0

    # Subcommand: cord cron
    if args.subcommand == "cron":
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
            status_color = "bold green" if j.enabled else "dim"
            table.add_row(
                j.id,
                j.name,
                j.schedule_expr,
                j.target_node,
                f"[{status_color}]{j.last_status}[/{status_color}]",
                next_s,
            )
        ui.console.print(table)
        ui.console.print("[dim]Use 'cord daemon' to run continuous scheduler in the background.[/dim]\n")
        return 0

    # Subcommand: cord ollama
    if args.subcommand == "ollama":
        from rich.table import Table
        from cord.models.ollama_manager import ollama_mgr
        running = ollama_mgr.is_running()
        if not running:
            ui.print_warning("Local Ollama daemon is OFFLINE or unreachable at http://127.0.0.1:11434.")
            ui.console.print("[dim]Run 'ollama serve' in your terminal or start the Ollama desktop app.[/dim]\n")
            return 0
        models = ollama_mgr.list_models()
        table = Table(title=f"🦙 CORD Ollama Local Models ({len(models)} Installed)", border_style="cyan")
        table.add_column("Model Name", style="bold cyan")
        table.add_column("Size", style="green")
        table.add_column("Digest", style="dim")
        table.add_column("Modified", style="white")
        for m in models:
            table.add_row(m["name"], m["size"], m["digest"], m["modified_at"])
        ui.console.print(table)
        ui.console.print(f"Ollama Daemon: [bold green]ONLINE[/bold green] at {ollama_mgr.base_url}")
        ui.console.print("[dim]Switch in chat with: /model ollama/<name> or /ollama[/dim]\n")
        return 0

    # Subcommand: cord voice
    if args.subcommand == "voice":
        from rich.table import Table
        from cord.voice.tts import tts
        cfg = tts.config
        table = Table(title="🎙️  CORD Voice Models & TTS Engine", border_style="magenta")
        table.add_column("Setting", style="bold cyan")
        table.add_column("Current Value", style="bold white")
        table.add_row("Provider", cfg.provider.upper())
        table.add_row("Model", cfg.model)
        table.add_row("Voice ID", cfg.voice_id)
        table.add_row("Speed Multiplier", f"{cfg.speed:.1f}x")
        table.add_row("Custom Base URL", cfg.base_url or "(default)")
        table.add_row("API Key Configured", "✓ Yes" if cfg.api_key else "No (using Edge-TTS or env)")
        ui.console.print(table)
        ui.console.print("[dim]Use '/voice' inside chat to configure providers or API keys.[/dim]\n")
        return 0

    # Subcommand: cord graph
    if args.subcommand == "graph":
        from cord.core.code_graph import code_graph_engine
        code_graph_engine.render_overview()
        return 0

    # Subcommand: cord impact
    if args.subcommand == "impact":
        from cord.core.code_graph import code_graph_engine
        target = " ".join(args.extra_args) if args.extra_args else "main.py"
        code_graph_engine.render_blast_radius(target)
        return 0

    # Subcommand: cord sentinel
    if args.subcommand == "sentinel":
        from cord.subagents.sentinel import community_sentinel
        if args.extra_args and args.extra_args[0] == "triage":
            topic = " ".join(args.extra_args[1:]) if len(args.extra_args) > 1 else "Community Feature"
            await community_sentinel.triage_proposal(
                title=topic,
                description=f"Community proposed feature/request: {topic}",
                source="cli",
            )
        else:
            community_sentinel.render_overview()
        return 0

    # Subcommand: cord radar
    if args.subcommand == "radar":
        from cord.core.tech_radar import tech_radar
        if args.extra_args and args.extra_args[0] == "install" and len(args.extra_args) > 1:
            res = tech_radar.install_mcp_server(args.extra_args[1])
            if res["success"]:
                ui.print_success(res["message"])
            else:
                ui.print_error(res["error"])
        else:
            tech_radar.render_radar()
        return 0

    # Subcommand: cord about
    if args.subcommand == "about":
        from cord.ui.about import show_about_screen
        await show_about_screen(cfg, animated=True)
        return 0

    # 3. Initialize Subagents Manager
    subagent_manager = None
    if cfg.enable_subagents:
        subagent_manager = SubagentManager(
            config=cfg,
            available_tools=tool_registry.tools,
        )
        tool_registry.register(SpawnSubagentTool(subagent_manager))
        tool_registry.register(CreateCustomSubagentTool(subagent_manager))
        tool_registry.register(CollaborativePlanTool(subagent_manager))
        tool_registry.register(SubagentDeliberateTool())
        tool_registry.register(RunParallelSubagentsTool(subagent_manager))
        if "swarm_dispatch" in tool_registry.tools:
            tool_registry.tools["swarm_dispatch"].subagent_manager = subagent_manager
        from cord.tools.dynamic_tool import dynamic_tool_manager
        dynamic_tool_manager.bind_registries(tool_registry=tool_registry, subagent_manager=subagent_manager)

    # 4. Initialize MCP Manager
    mcp_manager = None
    if cfg.enable_mcp:
        mcp_manager = MCPManager(workspace_path=Path(cfg.workspace_dir))
        await mcp_manager.initialize_all()
        tool_registry.register_many(mcp_manager.get_tools())

    # 5. Initialize Skills Loader
    skill_loader = None
    if cfg.enable_skills:
        skill_loader = SkillLoader(workspace_path=Path(cfg.workspace_dir))

    # Autonomous Closed-Loop Goal execution (-g "goal" or `cord agent "goal"`)
    goal_arg = args.goal or (" ".join(args.extra_args) if args.subcommand == "agent" and args.extra_args else None)
    if goal_arg:
        runtime = AgentRuntime(cfg, tool_registry)
        await runtime.run_goal(goal_arg)
        return 0

    # 6. Initialize Primary Agent
    agent = CordAgent(
        config=cfg,
        tool_registry=tool_registry,
        subagent_manager=subagent_manager,
        skill_loader=skill_loader,
    )

    # Live Voice Agent Mode (--live or `cord live`)
    if args.live or args.subcommand == "live":
        from cord.voice import LiveVoiceSession
        live_session = LiveVoiceSession(agent, cfg)
        await live_session.run()
        return 0

    # Daemon background scheduler mode (`cord daemon`)
    if args.subcommand == "daemon":
        from cord.cron.daemon import run_cron_daemon
        await run_cron_daemon(agent=agent)
        return 0

    # If single command mode (-c "do something")
    if args.command:
        ui.print_info(f"Executing: {args.command}")
        await agent.step(args.command)
        return 0

    # Otherwise launch interactive REPL
    repl = CordREPL(
        config_mgr=config_mgr,
        agent=agent,
        mcp_manager=mcp_manager,
        subagent_manager=subagent_manager,
        skill_loader=skill_loader,
    )

    try:
        await repl.run()
    finally:
        if mcp_manager:
            await mcp_manager.shutdown_all()

    return 0


def main() -> None:
    try:
        sys.exit(asyncio.run(main_async()))
    except KeyboardInterrupt:
        ui.print_info("\nExited.")
        sys.exit(0)


if __name__ == "__main__":
    main()
