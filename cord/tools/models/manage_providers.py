"""
CORD Tools - Model Provider Management Tool
Allows the autonomous agent to list, add, delete, test, and switch model providers dynamically.
"""

from __future__ import annotations
import json
from typing import Optional, List
from cord.tools.base import BaseTool, ToolResult
from cord.models.provider_manager import provider_mgr
from cord.core.config import ConfigManager


class ManageProvidersTool(BaseTool):
    name = "manage_providers"
    description = (
        "Manage AI model providers (Ollama, vLLM, LM Studio, OpenRouter, Together, custom endpoints). "
        "Supports 'list' (view all available providers), 'add' (register a new custom provider), "
        "'delete' (remove a custom provider), 'test' (verify connectivity to an endpoint), "
        "and 'switch' (hot-switch the active model provider for CORD)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "add", "delete", "test", "switch"],
                "description": "Provider management action to perform",
            },
            "name": {
                "type": "string",
                "description": "Unique identifier / name for the provider (e.g. 'vllm_local', 'openrouter', 'together')",
            },
            "base_url": {
                "type": "string",
                "description": "API Base URL (e.g. 'http://localhost:8000/v1' or 'https://openrouter.ai/api/v1')",
            },
            "api_key": {
                "type": "string",
                "description": "API key or environment variable name containing the key",
            },
            "default_model": {
                "type": "string",
                "description": "Default model name (e.g. 'meta-llama/Llama-3.3-70B-Instruct')",
            },
            "models": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional list of supported model tags/names",
            },
            "api_format": {
                "type": "string",
                "enum": ["openai", "anthropic", "gemini", "ollama"],
                "description": "Underlying API wire format (default: openai)",
            },
            "description": {
                "type": "string",
                "description": "Optional human-readable description for this provider",
            },
        },
        "required": ["action"],
    }

    def __init__(self, config_mgr: Optional[ConfigManager] = None):
        super().__init__()
        self.config_mgr = config_mgr or ConfigManager()

    async def execute(
        self,
        action: str,
        name: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        default_model: Optional[str] = None,
        models: Optional[List[str]] = None,
        api_format: str = "openai",
        description: str = "",
        **kwargs,
    ) -> ToolResult:
        if action == "list":
            providers = provider_mgr.list_providers(include_presets=True)
            summary = []
            for p in providers:
                ptype = "Custom" if p.get("is_custom") else "Preset"
                summary.append({
                    "id": p.get("id"),
                    "name": p.get("name"),
                    "type": ptype,
                    "base_url": p.get("base_url"),
                    "default_model": p.get("default_model"),
                    "models_count": len(p.get("models", [])),
                    "api_format": p.get("api_format"),
                })
            return ToolResult(
                success=True,
                output=json.dumps(summary, indent=2),
            )

        elif action == "add":
            if not name or not base_url:
                return ToolResult(
                    success=False,
                    output="Error: Both 'name' and 'base_url' are required to add a provider.",
                )
            res = provider_mgr.add_provider(
                name=name,
                base_url=base_url,
                api_key=api_key,
                default_model=default_model or "default",
                models=models,
                api_format=api_format or "openai",
                description=description or "",
            )
            return ToolResult(
                success=True,
                output=f"Successfully registered custom provider '{name}':\n{json.dumps(res, indent=2)}",
            )

        elif action == "delete":
            if not name:
                return ToolResult(
                    success=False,
                    output="Error: 'name' is required to delete a provider.",
                )
            deleted = provider_mgr.delete_provider(name)
            if deleted:
                return ToolResult(
                    success=True,
                    output=f"Successfully deleted custom provider '{name}'.",
                )
            return ToolResult(
                success=False,
                output=f"Provider '{name}' not found or is a protected built-in preset.",
            )

        elif action == "test":
            target = name or base_url
            if not target:
                return ToolResult(
                    success=False,
                    output="Error: Please specify 'name' or 'base_url' to test.",
                )
            test_res = provider_mgr.test_provider(target)
            if test_res.get("success"):
                return ToolResult(
                    success=True,
                    output=f"✔ Provider '{target}' is reachable!\n{json.dumps(test_res, indent=2)}",
                )
            return ToolResult(
                success=False,
                output=f"❌ Provider '{target}' connection failed:\n{json.dumps(test_res, indent=2)}",
            )

        elif action == "switch":
            if not name:
                return ToolResult(
                    success=False,
                    output="Error: 'name' is required to switch provider.",
                )
            cfg = provider_mgr.switch_to_provider(name, model=default_model, config_mgr=self.config_mgr)
            if cfg:
                return ToolResult(
                    success=True,
                    output=f"✔ Active provider switched to '{name}' (model: {cfg.model}, base_url: {cfg.base_url}).",
                )
            return ToolResult(
                success=False,
                output=f"Error: Provider '{name}' not found. Use action='list' to view available providers.",
            )

        return ToolResult(
            success=False,
            output=f"Unknown action: '{action}'. Supported actions: list, add, delete, test, switch.",
        )
