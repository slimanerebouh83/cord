"""
CORD CLI - Configuration Manager
Handles global (~/.cord/config.json) and workspace (.cord/config.json) configuration.
Supports cutting-edge 2025/2026 models: Claude 3.7 Sonnet, Gemini 2.5 Pro, DeepSeek R1, o3-mini, Grok 2, etc.
"""

from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field, asdict

# Preset provider configurations with modern 2025/2026 models
PROVIDER_PRESETS: Dict[str, Dict[str, Any]] = {
    "openrouter": {
        "name": "OpenRouter (All Modern Models)",
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "anthropic/claude-3.7-sonnet",
        "models": [
            "anthropic/claude-3.7-sonnet",
            "anthropic/claude-3.7-sonnet:thinking",
            "deepseek/deepseek-r1",
            "deepseek/deepseek-chat",
            "google/gemini-2.5-pro-exp-02-05",
            "google/gemini-2.0-flash-001",
            "openai/o3-mini",
            "openai/o1",
            "openai/gpt-4o-2024-11-20",
            "openai/gpt-4.5-preview",
            "qwen/qwen-2.5-coder-32b-instruct",
            "x-ai/grok-2-1212",
            "mistralai/codestral-2501",
            "meta-llama/llama-3.3-70b-instruct",
        ],
        "api_format": "openai",
        "api_key_url": "https://openrouter.ai/keys",
    },
    "deepseek": {
        "name": "DeepSeek Official",
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "api_format": "openai",
        "api_key_url": "https://platform.deepseek.com/api_keys",
    },
    "anthropic": {
        "name": "Anthropic Claude",
        "base_url": "https://api.anthropic.com/v1",
        "default_model": "claude-3-7-sonnet-20250219",
        "models": [
            "claude-3-7-sonnet-20250219",
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",
        ],
        "api_format": "anthropic",
        "api_key_url": "https://console.anthropic.com/settings/keys",
    },
    "openai": {
        "name": "OpenAI Official",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o",
        "models": [
            "o3-mini",
            "o1",
            "gpt-4.5-preview",
            "gpt-4o",
            "gpt-4o-mini",
        ],
        "api_format": "openai",
        "api_key_url": "https://platform.openai.com/api-keys",
    },
    "gemini": {
        "name": "Google Gemini API (OpenAI Compatible)",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "default_model": "gemini-2.5-flash",
        "models": [
            "gemini-2.5-flash",
            "gemini-2.5-pro",
            "gemini-2.5-pro-exp-02-05",
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite",
            "gemini-2.0-flash-thinking-exp-01-21",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
        ],
        "api_format": "openai",
        "api_key_url": "https://aistudio.google.com/app/apikey",
    },
    "xai": {
        "name": "xAI Grok",
        "base_url": "https://api.x.ai/v1",
        "default_model": "grok-2-1212",
        "models": [
            "grok-2-1212",
            "grok-2-vision-1212",
            "grok-beta",
        ],
        "api_format": "openai",
        "api_key_url": "https://console.x.ai/",
    },
    "ollama": {
        "name": "Ollama (Local Models)",
        "base_url": "http://localhost:11434/v1",
        "default_model": "qwen2.5-coder:latest",
        "models": [
            "qwen2.5-coder:latest",
            "deepseek-r1:latest",
            "llama3.3:latest",
            "mistral-small:latest",
        ],
        "api_format": "openai",
        "api_key_url": "Local (No Key Required)",
    },
    "groq": {
        "name": "Groq Ultra-Fast",
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "llama-3.3-70b-versatile",
        "models": [
            "llama-3.3-70b-versatile",
            "qwen-2.5-coder-32b",
            "deepseek-r1-distill-llama-70b",
        ],
        "api_format": "openai",
        "api_key_url": "https://console.groq.com/keys",
    },
    "together": {
        "name": "Together AI",
        "base_url": "https://api.together.xyz/v1",
        "default_model": "deepseek-ai/DeepSeek-R1",
        "models": [
            "deepseek-ai/DeepSeek-R1",
            "deepseek-ai/DeepSeek-V3",
            "meta-llama/Llama-3.3-70B-Instruct-Turbo",
            "Qwen/Qwen2.5-Coder-32B-Instruct",
        ],
        "api_format": "openai",
        "api_key_url": "https://api.together.xyz/settings/api-keys",
    },
    "moonshot": {
        "name": "Moonshot AI (Kimi)",
        "base_url": "https://api.moonshot.cn/v1",
        "default_model": "moonshot-v1-8k",
        "models": [
            "moonshot-v1-8k",
            "moonshot-v1-32k",
            "moonshot-v1-128k",
            "kimi-latest",
        ],
        "api_format": "openai",
        "api_key_url": "https://platform.moonshot.cn/console/api-keys",
    },
    "nvidia": {
        "name": "Nvidia NIM",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "default_model": "nvidia/nemotron-3-super-120b-a12b",
        "models": [
            "nvidia/nemotron-3-super-120b-a12b",
            "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
            "deepseek-ai/deepseek-r1",
            "meta/llama-3.3-70b-instruct",
            "nvidia/llama-3.1-nemotron-70b-instruct",
            "moonshotai/kimi-k3",
            "deepseek-ai/deepseek-v4-flash-0731",
            "openai/gpt-oss-20b",
        ],
        "api_format": "openai",
        "api_key_url": "https://build.nvidia.com/",
    },
    "mistral": {
        "name": "Mistral AI Official",
        "base_url": "https://api.mistral.ai/v1",
        "default_model": "codestral-latest",
        "models": [
            "codestral-latest",
            "mistral-large-latest",
            "pixtral-large-latest",
            "mistral-small-latest",
            "codestral-2501",
        ],
        "api_format": "openai",
        "api_key_url": "https://console.mistral.ai/api-keys",
    },
    "cerebras": {
        "name": "Cerebras Fast Inference",
        "base_url": "https://api.cerebras.ai/v1",
        "default_model": "llama-3.3-70b",
        "models": [
            "llama-3.3-70b",
            "llama-3.1-8b",
            "deepseek-r1-distill-llama-70b",
        ],
        "api_format": "openai",
        "api_key_url": "https://cloud.cerebras.ai/",
    },
    "sambanova": {
        "name": "SambaNova Cloud",
        "base_url": "https://api.sambanova.ai/v1",
        "default_model": "DeepSeek-R1",
        "models": [
            "DeepSeek-R1",
            "Meta-Llama-3.3-70B-Instruct",
            "Qwen2.5-Coder-32B-Instruct",
        ],
        "api_format": "openai",
        "api_key_url": "https://cloud.sambanova.ai/",
    },
    "cohere": {
        "name": "Cohere Command",
        "base_url": "https://api.cohere.com/v2",
        "default_model": "command-r-plus-08-2024",
        "models": [
            "command-r-plus-08-2024",
            "command-r-08-2024",
            "command-light",
        ],
        "api_format": "openai",
        "api_key_url": "https://dashboard.cohere.com/api-keys",
    },
    "custom": {
        "name": "Custom Endpoint (vLLM / LM Studio / Local)",
        "base_url": "http://localhost:8000/v1",
        "default_model": "custom-model",
        "models": ["custom-model"],
        "api_format": "openai",
        "api_key_url": "Custom",
    },
}

DEFAULT_DANGEROUS_COMMANDS = [
    r"rm\s+(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r)\s+.*",
    r"del\s+/[sS]\s+.*",
    r"rd\s+/[sS]\s+.*",
    r"format\s+[a-zA-Z]:",
    r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:",
    r"mkfs.*",
    r"dd\s+if=.*",
    r"shutdown.*",
]


def normalize_base_url(url: str) -> tuple[str, Optional[str]]:
    """
    Cleans and normalizes an API Base URL.
    Returns:
        (clean_url, reason_note)

    Why this is needed:
    OpenAI-compatible clients (including CORD) automatically append '/chat/completions'
    (or '/messages' for Anthropic) to the configured Base URL. If a user enters
    'https://openrouter.ai/api/v1/chat/completions', keeping that suffix would cause
    requests to hit 'https://openrouter.ai/api/v1/chat/completions/chat/completions',
    resulting in HTTP 404 (Not Found).
    This function cleanly removes redundant endpoint paths and produces an informative notice.
    """
    raw = (url or "").strip().rstrip("/")
    if not raw:
        return raw, None

    # Auto-correct common Google/Gemini URL typos
    if "googleapis.com" in raw and "generativelanguage" not in raw:
        return "https://generativelanguage.googleapis.com/v1beta/openai", "Corrected Gemini endpoint to https://generativelanguage.googleapis.com/v1beta/openai"

    note = None
    if raw.endswith("/chat/completions"):
        raw = raw[:-17].rstrip("/")
        note = "Automatically trimmed '/chat/completions' because CORD appends it automatically (avoids duplicate path HTTP 404 errors)."
    elif raw.endswith("/chat"):
        raw = raw[:-5].rstrip("/")
        note = "Automatically trimmed '/chat' because CORD appends '/chat/completions' automatically."
    elif raw.endswith("/messages"):
        raw = raw[:-9].rstrip("/")
        note = "Automatically trimmed '/messages' because CORD appends '/messages' automatically for Anthropic format."

    return raw, note


@dataclass
class CordConfig:
    provider: str = "openrouter"
    base_url: str = "https://openrouter.ai/api/v1"
    api_key: str = ""
    model: str = "anthropic/claude-3.7-sonnet"
    api_format: str = "openai"  # "openai" or "anthropic"
    
    # Permission Mode: "strict" (ask all), "balanced" (ask writes/shell), "yolo" (auto all safe)
    permission_mode: str = "yolo"
    
    # Appearance & UI
    theme: str = "cyberpunk"  # "cyberpunk", "monokai", "dracula", "nord", "neon"
    stream_output: bool = True
    show_thinking: bool = True
    show_token_cost: bool = True
    
    # Model parameters
    temperature: float = 0.2
    max_tokens: int = 16384
    
    # Continuous Deep Thinking & Reasoning configuration
    always_think: bool = True
    reasoning_effort: str = "high"  # "low", "medium", "high"
    thinking_budget: int = 16000    # Tokens allocated for deep reasoning (Claude 3.7, o1, o3, etc.)
    
    # Workspace & Path configs
    workspace_dir: str = field(default_factory=lambda: str(Path.cwd()))
    dangerous_patterns: List[str] = field(default_factory=lambda: list(DEFAULT_DANGEROUS_COMMANDS))
    
    # Subagents, MCP & Skills
    enable_subagents: bool = True
    enable_mcp: bool = True
    enable_skills: bool = True
    enable_web_tools: bool = True
    auto_compact_context: bool = True
    
    # Operational Mode: "agent" (default), "coder", "computer", "fast"
    active_mode: str = "agent"

    # Multi-language & UI
    language: Optional[str] = None  # "ar", "en", "fr", "es", "de", "zh", "ja", "ru", "tr" (None = first run)
    input_engine: str = "auto"      # "auto", "native" (perfect Arabic/RTL), "advanced" (prompt_toolkit)
    thinking_mode: str = "stream"   # "stream" (live reasoning), "spinner", "off"

    # Saved models for quick switching
    saved_models: Dict[str, Dict[str, str]] = field(default_factory=lambda: {
        "nvidia-nemotron": {"model": "nvidia/nemotron-3-super-120b-a12b", "provider": "custom", "base_url": "https://integrate.api.nvidia.com/v1", "name": "Nvidia Nemotron 3 Super 120B (Active & Ultra-Fast)"},
        "nvidia-fast": {"model": "openai/gpt-oss-20b", "provider": "custom", "base_url": "https://integrate.api.nvidia.com/v1", "name": "Nvidia GPT-OSS 20B (Ultra-Fast 3s)"},
        "nvidia-deepseek": {"model": "deepseek-ai/deepseek-v4-flash-0731", "provider": "custom", "base_url": "https://integrate.api.nvidia.com/v1", "name": "Nvidia DeepSeek v4 Flash"},
        "nvidia-kimi": {"model": "moonshotai/kimi-k3", "provider": "custom", "base_url": "https://integrate.api.nvidia.com/v1", "name": "Nvidia Kimi-K3 (Queue Overloaded on NVIDIA)"},
        "claude-sonnet": {"model": "anthropic/claude-3.7-sonnet", "provider": "openrouter", "base_url": "https://openrouter.ai/api/v1", "name": "Claude 3.7 Sonnet (Hybrid Reasoning)"},
        "claude-sonnet4": {"model": "anthropic/claude-sonnet-4", "provider": "openrouter", "base_url": "https://openrouter.ai/api/v1", "name": "Claude Sonnet 4 (Latest)"},
        "claude-thinking": {"model": "anthropic/claude-3.7-sonnet:thinking", "provider": "openrouter", "base_url": "https://openrouter.ai/api/v1", "name": "Claude 3.7 Sonnet Thinking"},
        "hermes": {"model": "nousresearch/hermes-3-llama-3.1-405b", "provider": "openrouter", "base_url": "https://openrouter.ai/api/v1", "name": "Agent Hermes 3 (405B Autonomous)"},
        "deepseek-r1": {"model": "deepseek/deepseek-r1", "provider": "openrouter", "base_url": "https://openrouter.ai/api/v1", "name": "DeepSeek R1 (Reasoning SOTA)"},
        "deepseek-v3": {"model": "deepseek/deepseek-chat", "provider": "openrouter", "base_url": "https://openrouter.ai/api/v1", "name": "DeepSeek V3 (671B MoE)"},
        "gemini-2-5": {"model": "google/gemini-2.5-pro-exp-02-05", "provider": "openrouter", "base_url": "https://openrouter.ai/api/v1", "name": "Google Gemini 2.5 Pro"},
        "gemini-flash": {"model": "google/gemini-2.0-flash-001", "provider": "openrouter", "base_url": "https://openrouter.ai/api/v1", "name": "Google Gemini 2.0 Flash"},
        "o3-mini": {"model": "openai/o3-mini", "provider": "openrouter", "base_url": "https://openrouter.ai/api/v1", "name": "OpenAI o3-mini (Reasoning & Code)"},
        "gpt4o": {"model": "gpt-4o", "provider": "openai", "base_url": "https://api.openai.com/v1", "name": "OpenAI GPT-4o"},
        "kimi-k1-5": {"model": "moonshotai/kimi-k1.5", "provider": "openrouter", "base_url": "https://openrouter.ai/api/v1", "name": "Moonshot Kimi k1.5"},
        "kimi-128k": {"model": "moonshot-v1-128k", "provider": "moonshot", "base_url": "https://api.moonshot.cn/v1", "name": "Kimi 128K Long Context"},
        "qwen-coder": {"model": "qwen/qwen-2.5-coder-32b-instruct", "provider": "openrouter", "base_url": "https://openrouter.ai/api/v1", "name": "Qwen 2.5 Coder 32B"},
    })

    # Custom headers for API requests
    extra_headers: Dict[str, str] = field(default_factory=dict)
    
    # Auto-Failover (Disabled - CORD sticks strictly to the user's selected model and reconnects on error)
    auto_failover: bool = False
    fallback_model: Optional[str] = None

    def get_fallback_candidate(self) -> Optional[Dict[str, str]]:
        """Returns None because automatic model switching is disabled; CORD reconnects with the same model."""
        return None

    def is_configured(self) -> bool:
        """Returns True if the config has valid minimum parameters to make calls."""
        if self.provider == "ollama":
            return bool(self.base_url and self.model)
        return bool(self.api_key and self.base_url and self.model)

    def __post_init__(self):
        if self.base_url:
            clean, _ = normalize_base_url(self.base_url)
            self.base_url = clean


class ConfigManager:
    """Manages reading and writing configuration files."""

    def __init__(self, workspace_path: Optional[Path] = None, home_cord_dir: Optional[Path] = None):
        self.home_cord_dir = home_cord_dir or (Path.home() / ".cord")
        self.global_config_path = self.home_cord_dir / "config.json"
        self.workspace_path = workspace_path or Path.cwd()
        self.local_config_path = self.workspace_path / ".cord" / "config.json"
        self._ensure_dirs()
        self.config = self.load_config()

    def _ensure_dirs(self) -> None:
        self.home_cord_dir.mkdir(parents=True, exist_ok=True)
        (self.home_cord_dir / "skills").mkdir(parents=True, exist_ok=True)
        (self.home_cord_dir / "sessions").mkdir(parents=True, exist_ok=True)
        (self.home_cord_dir / "backups").mkdir(parents=True, exist_ok=True)

    def load_config(self) -> CordConfig:
        """Loads configuration, merging global with local workspace overrides."""
        merged_data: Dict[str, Any] = {}

        # 1. Global config
        if self.global_config_path.exists():
            try:
                with open(self.global_config_path, "r", encoding="utf-8") as f:
                    merged_data.update(json.load(f))
            except Exception:
                pass

        # 2. Local workspace config overrides
        if self.local_config_path.exists():
            try:
                with open(self.local_config_path, "r", encoding="utf-8") as f:
                    merged_data.update(json.load(f))
            except Exception:
                pass

        # 3. Environment variable overrides
        if "CORD_API_KEY" in os.environ:
            merged_data["api_key"] = os.environ["CORD_API_KEY"]
        elif "OPENAI_API_KEY" in os.environ and not merged_data.get("api_key"):
            merged_data["api_key"] = os.environ["OPENAI_API_KEY"]
        elif "ANTHROPIC_API_KEY" in os.environ and not merged_data.get("api_key"):
            merged_data["api_key"] = os.environ["ANTHROPIC_API_KEY"]
        elif "GEMINI_API_KEY" in os.environ and not merged_data.get("api_key"):
            merged_data["api_key"] = os.environ["GEMINI_API_KEY"]

        if "CORD_BASE_URL" in os.environ:
            merged_data["base_url"] = os.environ["CORD_BASE_URL"]
        if "CORD_MODEL" in os.environ:
            merged_data["model"] = os.environ["CORD_MODEL"]

        # Instantiate dataclass with filtered recognized fields
        valid_keys = {f.name for f in CordConfig.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in merged_data.items() if k in valid_keys}
        filtered_data["workspace_dir"] = str(self.workspace_path)
        
        return CordConfig(**filtered_data)

    def save_global_config(self, config: Optional[CordConfig] = None) -> None:
        """Saves current or specified config to global ~/.cord/config.json."""
        target = config or self.config
        data = asdict(target)
        self.home_cord_dir.mkdir(parents=True, exist_ok=True)
        with open(self.global_config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def save_global(self, config: Optional[CordConfig] = None) -> None:
        """Convenience alias for save_global_config."""
        self.save_global_config(config)

    def save_local_config(self, config: Optional[CordConfig] = None) -> None:
        """Saves config to workspace .cord/config.json."""
        target = config or self.config
        data = asdict(target)
        local_dir = self.workspace_path / ".cord"
        local_dir.mkdir(parents=True, exist_ok=True)
        with open(self.local_config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def save_local(self, config: Optional[CordConfig] = None) -> None:
        """Convenience alias for save_local_config."""
        self.save_local_config(config)

    def update(self, **kwargs) -> CordConfig:
        """Updates in-memory config and writes to global file."""
        for k, v in kwargs.items():
            if hasattr(self.config, k):
                setattr(self.config, k, v)
        self.save_global_config(self.config)
        return self.config
