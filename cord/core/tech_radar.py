"""
CORD Internet Tech Radar - Frontier AI & MCP Marketplace Explorer
Tracks emerging frontier AI models, cutting-edge coding paradigms, and curated
Model Context Protocol (MCP) servers with 1-click configuration.
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from rich.table import Table
from rich.panel import Panel

from cord.ui.console import ui


# Curated 2025/2026 Frontier Models Catalog
FRONTIER_MODELS: List[Dict[str, Any]] = [
    {
        "id": "anthropic/claude-3-7-sonnet",
        "name": "Claude 3.7 Sonnet",
        "provider": "Anthropic / OpenRouter",
        "category": "Hybrid Reasoning & Surgical Coding",
        "swe_bench": "70.3%",
        "context": "200K",
        "strengths": "Extended live thinking, precise code edits, zero hallucination",
    },
    {
        "id": "google/gemini-2.5-flash",
        "name": "Gemini 2.5 Flash",
        "provider": "Google Gemini",
        "category": "Ultra-Fast Frontier Coding",
        "swe_bench": "65.8%",
        "context": "1,000,000",
        "strengths": "Lightning speed (150+ t/s), massive codebase context, vision",
    },
    {
        "id": "deepseek/deepseek-r1",
        "name": "DeepSeek R1",
        "provider": "DeepSeek / OpenRouter",
        "category": "Pure Open-Weights Reasoning",
        "swe_bench": "67.2%",
        "context": "128K",
        "strengths": "Deep mathematical deduction, RL reasoning, highly economical",
    },
    {
        "id": "qwen/qwen2.5-coder-32b-instruct",
        "name": "Qwen 2.5 Coder 32B",
        "provider": "Ollama / OpenRouter",
        "category": "Local & Offline Coding Titan",
        "swe_bench": "61.5%",
        "context": "128K",
        "strengths": "Runs locally on consumer GPUs, top-tier Python & Rust syntax",
    },
    {
        "id": "openai/o3-mini",
        "name": "OpenAI o3-mini",
        "provider": "OpenAI",
        "category": "High-Density STEM Reasoning",
        "swe_bench": "69.1%",
        "context": "200K",
        "strengths": "Algorithmic puzzles, competition coding, multi-step proofs",
    },
]

# Curated MCP Servers Marketplace
MCP_MARKETPLACE: Dict[str, Dict[str, Any]] = {
    "github": {
        "name": "GitHub MCP Server",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}"},
        "description": "Full repository browsing, PR management, issues triage, and git search.",
        "category": "Developer Tools",
    },
    "postgres": {
        "name": "PostgreSQL MCP Server",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-postgres", "postgresql://localhost/mydb"],
        "env": {},
        "description": "Direct read-only schema inspection, table analysis, and query execution.",
        "category": "Databases",
    },
    "puppeteer": {
        "name": "Puppeteer Web Automation",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-puppeteer"],
        "env": {},
        "description": "Headless browser control, web page scraping, and visual screenshot capture.",
        "category": "Web Automation",
    },
    "brave-search": {
        "name": "Brave Web Search",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-brave-search"],
        "env": {"BRAVE_API_KEY": "${BRAVE_API_KEY}"},
        "description": "Real-time internet search across news, documentation, and technical forums.",
        "category": "Internet & Search",
    },
    "filesystem": {
        "name": "Sandboxed Filesystem",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "."],
        "env": {},
        "description": "Secure multi-directory file operations and directory watching.",
        "category": "System",
    },
    "memory": {
        "name": "Knowledge Graph Memory",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-memory"],
        "env": {},
        "description": "Persistent graph memory across coding sessions to preserve architectural rules.",
        "category": "Agent Memory",
    },
}


class InternetTechRadar:
    """Manages frontier model tracking and 1-click MCP server marketplace installation."""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or (Path.home() / ".cord" / "mcp_servers.json")

    def install_mcp_server(self, server_key: str) -> Dict[str, Any]:
        """Installs an MCP server by writing its configuration into ~/.cord/mcp_servers.json."""
        clean_key = server_key.strip().lower()
        if clean_key not in MCP_MARKETPLACE:
            return {
                "success": False,
                "error": f"Unknown MCP server '{server_key}'. Available: {list(MCP_MARKETPLACE.keys())}",
            }

        spec = MCP_MARKETPLACE[clean_key]
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        current_cfg: Dict[str, Any] = {"mcpServers": {}}
        if self.config_path.exists():
            try:
                current_cfg = json.loads(self.config_path.read_text(encoding="utf-8"))
            except Exception:
                current_cfg = {"mcpServers": {}}

        if "mcpServers" not in current_cfg:
            current_cfg["mcpServers"] = {}

        current_cfg["mcpServers"][clean_key] = {
            "command": spec["command"],
            "args": spec["args"],
            "env": spec.get("env", {}),
        }

        self.config_path.write_text(json.dumps(current_cfg, indent=2), encoding="utf-8")
        return {
            "success": True,
            "message": f"Successfully configured '{spec['name']}' in {self.config_path}!",
            "server": clean_key,
        }

    def render_radar(self) -> None:
        """Renders the comprehensive Tech Radar visual dashboard."""
        ui.console.print(Panel(
            "[bold #38bdf8]⚡ CORD INTERNET TECH RADAR & FRONTIER AI INTELLIGENCE[/bold #38bdf8]\n"
            "[dim]Tracking emerging frontier models, MCP tools, and autonomous coding breakthroughs.[/dim]",
            border_style="#6366f1",
        ))

        # 1. Frontier Models
        m_table = Table(title="🧠 Frontier Coding & Reasoning Models (2025/2026)", border_style="cyan")
        m_table.add_column("Model Name", style="bold white", width=22)
        m_table.add_column("Provider", style="magenta", width=18)
        m_table.add_column("Category", style="cyan", width=26)
        m_table.add_column("SWE-bench", justify="center", style="green", width=12)
        m_table.add_column("Context", justify="center", style="yellow", width=12)
        m_table.add_column("Superpower", style="dim white")

        for m in FRONTIER_MODELS:
            m_table.add_row(
                m["name"],
                m["provider"],
                m["category"],
                m["swe_bench"],
                m["context"],
                m["strengths"],
            )
        ui.console.print(m_table)

        # 2. Curated MCP Marketplace
        p_table = Table(title="🔌 Curated Model Context Protocol (MCP) Server Marketplace", border_style="green")
        p_table.add_column("Key", style="bold yellow", width=14)
        p_table.add_column("Server Name", style="bold white", width=24)
        p_table.add_column("Category", style="cyan", width=16)
        p_table.add_column("Capabilities", style="dim white")
        p_table.add_column("Install Command", style="magenta")

        for k, v in MCP_MARKETPLACE.items():
            p_table.add_row(
                k,
                v["name"],
                v["category"],
                v["description"],
                f"/radar install {k}",
            )
        ui.console.print(p_table)
        ui.console.print("[dim]Use [bold cyan]/radar install <key>[/bold cyan] to install any MCP server into your local environment.[/dim]\n")


tech_radar = InternetTechRadar()
