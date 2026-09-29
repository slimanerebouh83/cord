"""CORD Model Router - Dynamic Role-Based Model Selection & Auto-Routing"""
from __future__ import annotations
import os
from enum import Enum
from typing import Optional, Dict
from cord.models.capabilities import ModelCapability, model_capability_registry
from cord.models.model_resolver import model_resolver
from cord.providers.provider_manager import provider_manager

class ModelRole(str, Enum):
    FAST = "FAST"              # Quick summaries, file listing, formatting
    CODING = "CODING"          # Code synthesis, editing, refactoring
    REASONING = "REASONING"    # Multi-step planning, complex debugging
    VISION = "VISION"          # Image analysis, GUI computer use
    FALLBACK = "FALLBACK"      # Guaranteed fallback model

class ModelRouter:
    """Routes requests to the optimal model based on capability, cost, and availability."""

    def __init__(self, default_model: Optional[str] = None):
        self.default_model = default_model or os.environ.get("CORD_MODEL") or "auto"
        self._role_overrides: Dict[ModelRole, str] = {}

    def set_role_model(self, role: ModelRole, model_name: str):
        self._role_overrides[role] = model_name

    def resolve_for_role(self, role: ModelRole, preferred_model: Optional[str] = None) -> str:
        """Determines the best model string for a given operational role."""
        if preferred_model and preferred_model != "auto":
            return preferred_model

        if role in self._role_overrides:
            return self._role_overrides[role]

        # Check configured default if explicit
        if self.default_model and self.default_model != "auto":
            # If vision is requested, ensure model has vision capability or find vision fallback
            if role == ModelRole.VISION:
                caps = model_capability_registry.get_capabilities(self.default_model)
                if ModelCapability.VISION not in caps:
                    # Choose a known vision capable model from available providers
                    if provider_manager.get_active_api_key("openrouter"):
                        return "openrouter/anthropic/claude-3.5-sonnet"
                    elif provider_manager.get_active_api_key("openai"):
                        return "gpt-4o"
                    elif provider_manager.get_active_api_key("groq"):
                        return "groq/llama-3.2-11b-vision-preview"
            return self.default_model

        # Dynamic discovery based on active providers
        providers = provider_manager.discover_providers()
        active_names = [p.name for p in providers if p.is_configured]

        if "openrouter" in active_names:
            if role == ModelRole.FAST:
                return "openrouter/meta-llama/llama-3.1-8b-instruct"
            elif role == ModelRole.CODING:
                return "openrouter/anthropic/claude-3.5-sonnet"
            elif role == ModelRole.REASONING:
                return "openrouter/deepseek/deepseek-r1"
            elif role == ModelRole.VISION:
                return "openrouter/anthropic/claude-3.5-sonnet"
            return "openrouter/auto"

        if "groq" in active_names:
            if role == ModelRole.FAST:
                return "groq/llama-3.1-8b-instant"
            elif role == ModelRole.VISION:
                return "groq/llama-3.2-11b-vision-preview"
            return "groq/openai/gpt-oss-120b"

        if "openai" in active_names:
            if role == ModelRole.FAST:
                return "gpt-4o-mini"
            return "gpt-4o"

        if "anthropic" in active_names:
            if role == ModelRole.FAST:
                return "claude-3-5-haiku-20241022"
            return "claude-3-5-sonnet-20241022"

        if "deepseek" in active_names:
            if role == ModelRole.REASONING:
                return "deepseek/deepseek-reasoner"
            return "deepseek/deepseek-chat"

        if "ollama" in active_names:
            return "ollama/qwen2.5-coder:7b"

        # Universal fallback
        return self.default_model or "auto"

model_router = ModelRouter()
