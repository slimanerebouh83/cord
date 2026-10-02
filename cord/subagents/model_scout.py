"""
CORD Subagents - Model Scout
Tracks, discovers, benchmarks, and updates the latest cutting-edge AI models
across Anthropic Claude, DeepSeek, Google Gemini, OpenAI, Moonshot Kimi, Qwen, and more.
"""

from __future__ import annotations
import httpx
from typing import Dict, Any, List, Optional
from rich.table import Table
from rich.panel import Panel

from cord.ui.console import ui
from cord.core.config import ConfigManager

# State-of-the-art 2025/2026 Model Intelligence Catalog
LATEST_MODELS_CATALOG: Dict[str, Dict[str, Any]] = {
    # 1. Anthropic Claude
    "claude-3-7-sonnet": {
        "id": "anthropic/claude-3.7-sonnet",
        "provider": "openrouter",
        "name": "Claude 3.7 Sonnet (Hybrid Reasoning)",
        "org": "Anthropic",
        "context": "200K",
        "features": "Hybrid Fast/Thinking, SOTA Coding & Architecture",
        "release": "2025",
    },
    "claude-3-7-thinking": {
        "id": "anthropic/claude-3.7-sonnet:thinking",
        "provider": "openrouter",
        "name": "Claude 3.7 Sonnet Thinking",
        "org": "Anthropic",
        "context": "200K",
        "features": "Deep CoT Reasoning, Autonomous Coding",
        "release": "2025",
    },
    "claude-3-5-sonnet": {
        "id": "anthropic/claude-3.5-sonnet",
        "provider": "openrouter",
        "name": "Claude 3.5 Sonnet v2",
        "org": "Anthropic",
        "context": "200K",
        "features": "Industry Benchmark for Code and Tool Calling",
        "release": "Late 2024",
    },
    "claude-3-5-haiku": {
        "id": "anthropic/claude-3.5-haiku",
        "provider": "openrouter",
        "name": "Claude 3.5 Haiku",
        "org": "Anthropic",
        "context": "200K",
        "features": "Ultra-fast response latency, compact footprint",
        "release": "2024/2025",
    },

    # 2. DeepSeek
    "deepseek-r1": {
        "id": "deepseek/deepseek-r1",
        "provider": "openrouter",
        "name": "DeepSeek R1 (Open Reasoning SOTA)",
        "org": "DeepSeek",
        "context": "128K",
        "features": "Pure Reinforcement Learning Reasoning, Math & Code",
        "release": "2025",
    },
    "deepseek-v3": {
        "id": "deepseek/deepseek-chat",
        "provider": "openrouter",
        "name": "DeepSeek V3 (671B MoE)",
        "org": "DeepSeek",
        "context": "128K",
        "features": "Top-tier Generalist & Coding, Multi-token prediction",
        "release": "2025",
    },
    "deepseek-v4-fast": {
        "id": "deepseek-ai/deepseek-v4-flash-0731",
        "provider": "custom",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "name": "Nvidia DeepSeek v4 Flash",
        "org": "DeepSeek / Nvidia",
        "context": "128K",
        "features": "Nvidia NIM Accelerated Endpoint",
        "release": "2025",
    },

    # 3. Google Gemini
    "gemini-2-5-flash": {
        "id": "gemini-2.5-flash",
        "provider": "gemini",
        "name": "Gemini 2.5 Flash",
        "org": "Google",
        "context": "1M+",
        "features": "Next-generation ultra-fast multimodal intelligence & code",
        "release": "2025",
    },
    "gemini-2-5-pro": {
        "id": "google/gemini-2.5-pro-exp-02-05",
        "provider": "openrouter",
        "name": "Gemini 2.5 Pro Experimental",
        "org": "Google",
        "context": "1M+",
        "features": "Massive Context Window, SOTA Multimodal & Code",
        "release": "2025",
    },
    "gemini-2-flash": {
        "id": "google/gemini-2.0-flash-001",
        "provider": "openrouter",
        "name": "Gemini 2.0 Flash",
        "org": "Google",
        "context": "1M",
        "features": "Sub-second TTFT, High throughput, Multimodal",
        "release": "2025",
    },
    "gemini-2-thinking": {
        "id": "google/gemini-2.0-flash-thinking-exp-01-21",
        "provider": "openrouter",
        "name": "Gemini 2.0 Flash Thinking",
        "org": "Google",
        "context": "1M",
        "features": "Live Thinking Process, Complex Math & Logic",
        "release": "2025",
    },

    # 4. OpenAI
    "o3-mini": {
        "id": "openai/o3-mini",
        "provider": "openrouter",
        "name": "OpenAI o3-mini (STEM & Code)",
        "org": "OpenAI",
        "context": "200K",
        "features": "High-efficiency deliberate reasoning, competitive coding",
        "release": "2025",
    },
    "o1": {
        "id": "openai/o1",
        "provider": "openrouter",
        "name": "OpenAI o1 Full",
        "org": "OpenAI",
        "context": "200K",
        "features": "Deep reasoning across science, coding, and strategy",
        "release": "Late 2024",
    },
    "gpt-4-5": {
        "id": "openai/gpt-4.5-preview",
        "provider": "openrouter",
        "name": "GPT-4.5 Preview (Orion)",
        "org": "OpenAI",
        "context": "128K",
        "features": "Next-gen flagship foundation model",
        "release": "2025",
    },
    "gpt-4o": {
        "id": "openai/gpt-4o",
        "provider": "openrouter",
        "name": "GPT-4o Omnimodel",
        "org": "OpenAI",
        "context": "128K",
        "features": "Omni-modal text/vision flagship",
        "release": "2024/2025",
    },

    # 5. Moonshot AI / Kimi
    "kimi-k1-5": {
        "id": "moonshotai/kimi-k1.5",
        "provider": "openrouter",
        "name": "Kimi k1.5 (Moonshot Reasoning SOTA)",
        "org": "Moonshot AI",
        "context": "128K",
        "features": "Multimodal long-context reasoning, Math & Code",
        "release": "2025",
    },
    "kimi-128k": {
        "id": "moonshot-v1-128k",
        "provider": "moonshot",
        "base_url": "https://api.moonshot.cn/v1",
        "name": "Kimi 128K Long Context",
        "org": "Moonshot AI",
        "context": "128K",
        "features": "Ultra-long document retrieval & Chinese/English analysis",
        "release": "2024/2025",
    },

    # 6. Alibaba Qwen
    "qwen-2-5-coder": {
        "id": "qwen/qwen-2.5-coder-32b-instruct",
        "provider": "openrouter",
        "name": "Qwen 2.5 Coder 32B Instruct",
        "org": "Alibaba",
        "context": "128K",
        "features": "Code generation, repository editing & refactoring",
        "release": "Late 2024/2025",
    },
    "qwq-32b": {
        "id": "qwen/qwq-32b-preview",
        "provider": "openrouter",
        "name": "QwQ 32B Reasoning Preview",
        "org": "Alibaba",
        "context": "32K",
        "features": "Open weights deep reasoning rivaling o1-mini",
        "release": "2025",
    },

    # 7. Nvidia Accelerated Fast Fallbacks
    "nvidia-fast": {
        "id": "openai/gpt-oss-20b",
        "provider": "custom",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "name": "Nvidia GPT-OSS 20B (Ultra-Fast 3s)",
        "org": "Nvidia NIM",
        "context": "64K",
        "features": "Instant 3.3s response time, automatic failover target",
        "release": "2025",
    },
}


class ModelScoutSubagent:
    """Subagent specialized in AI model scouting, discovery, and automatic bookmarking."""

    def __init__(self, config_mgr: ConfigManager):
        self.config_mgr = config_mgr

    def get_catalog(self, filter_org: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """Returns models catalog optionally filtered by organization."""
        if not filter_org:
            return LATEST_MODELS_CATALOG
        org_clean = filter_org.strip().lower()
        return {
            alias: data for alias, data in LATEST_MODELS_CATALOG.items()
            if org_clean in data.get("org", "").lower() or org_clean in alias.lower()
        }

    def update_saved_models_in_config(self) -> int:
        """Registers all cutting-edge catalog presets into the user's ~/.cord/config.json."""
        cfg = self.config_mgr.config
        added_count = 0

        for alias, data in LATEST_MODELS_CATALOG.items():
            preset_obj = {
                "model": data["id"],
                "provider": data.get("provider", "openrouter"),
                "name": data["name"],
            }
            if "base_url" in data:
                preset_obj["base_url"] = data["base_url"]

            if alias not in cfg.saved_models or cfg.saved_models[alias].get("model") != data["id"]:
                cfg.saved_models[alias] = preset_obj
                added_count += 1

        self.config_mgr.save_global_config(cfg)
        return added_count

    def render_catalog_table(self, filter_org: Optional[str] = None) -> None:
        """Prints a stylish rich table of discovered modern AI models."""
        catalog = self.get_catalog(filter_org)
        title_extra = f" ({filter_org})" if filter_org else ""
        table = Table(
            title=f"🚀 2025/2026 AI Model Intelligence Catalog{title_extra}",
            show_header=True,
            header_style="bold bright_cyan",
            border_style="#6366f1",
            box=None,
            padding=(0, 2),
        )
        table.add_column("Alias", style="bold yellow", width=22)
        table.add_column("Org / Lab", style="bold white", width=14)
        table.add_column("Model ID", style="cyan", width=38)
        table.add_column("Context", style="green", justify="center", width=10)
        table.add_column("Key Highlights & Features", style="dim")

        cur_model = self.config_mgr.config.model
        for alias, info in catalog.items():
            is_cur = " [bold green]◄ CURRENT[/bold green]" if info["id"] == cur_model else ""
            table.add_row(
                f"{alias}{is_cur}",
                info.get("org", ""),
                info["id"],
                info.get("context", "128K"),
                info.get("features", "")
            )

        ui.console.print("\n")
        ui.console.print(Panel(table, border_style="bright_blue", padding=(0, 1)))
        ui.console.print("[dim]Switch to any model: /model <alias> (e.g. /model claude-3-7, /model gemini-2-5, /model deepseek-r1)[/dim]\n")
