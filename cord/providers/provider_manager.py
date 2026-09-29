"""
CORD Providers - Dynamic Provider Manager
Discovers API keys and endpoints from environment and config without hardcoded constraints.
"""

from __future__ import annotations
import os
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class ProviderInfo:
    name: str
    env_var: str
    is_configured: bool
    masked_key: str = ""
    base_url: Optional[str] = None


class ProviderManager:
    """Manages AI provider environment and discovery dynamically."""

    COMMON_PROVIDERS = [
        ("groq", "GROQ_API_KEY"),
        ("openai", "OPENAI_API_KEY"),
        ("anthropic", "ANTHROPIC_API_KEY"),
        ("gemini", "GEMINI_API_KEY"),
        ("deepseek", "DEEPSEEK_API_KEY"),
        ("openrouter", "OPENROUTER_API_KEY"),
        ("mistral", "MISTRAL_API_KEY"),
        ("xai", "XAI_API_KEY"),
        ("together_ai", "TOGETHERAI_API_KEY"),
        ("ollama", "OLLAMA_API_BASE"),
    ]

    @staticmethod
    def mask_key(key: str) -> str:
        if not key:
            return "(not set)"
        if len(key) <= 8:
            return "***"
        return f"{key[:4]}...{key[-4:]}"

    @classmethod
    def get_configured_providers(cls, extra_keys: Optional[Dict[str, str]] = None) -> List[ProviderInfo]:
        """Scans environment and custom keys to determine active providers."""
        results: List[ProviderInfo] = []
        extra_keys = extra_keys or {}

        for prov_name, env_var in cls.COMMON_PROVIDERS:
            val = os.environ.get(env_var) or extra_keys.get(prov_name) or extra_keys.get(env_var)
            is_conf = bool(val) or (prov_name == "ollama")
            results.append(
                ProviderInfo(
                    name=prov_name,
                    env_var=env_var,
                    is_configured=is_conf,
                    masked_key=cls.mask_key(val) if val else ("local" if prov_name == "ollama" else "(not set)"),
                )
            )

        # Detect any other *_API_KEY in environment dynamically
        known_vars = {p[1] for p in cls.COMMON_PROVIDERS}
        for env_k, env_v in os.environ.items():
            if env_k.endswith("_API_KEY") and env_k not in known_vars:
                name = env_k[:-8].lower()
                results.append(
                    ProviderInfo(
                        name=name,
                        env_var=env_k,
                        is_configured=bool(env_v),
                        masked_key=cls.mask_key(env_v),
                    )
                )

        return results

    def resolve_api_key(self, provider: str) -> Optional[str]:
        """Resolves API key for a given provider from environment variables."""
        for prov_name, env_var in self.COMMON_PROVIDERS:
            if prov_name == provider:
                return os.environ.get(env_var) or None
        # Check dynamically named env vars
        env_key = f"{provider.upper()}_API_KEY"
        return os.environ.get(env_key) or None

    def discover_providers(self) -> List[ProviderInfo]:
        return self.get_configured_providers()

    def get_active_api_key(self, provider: str) -> Optional[str]:
        return self.resolve_api_key(provider)

provider_manager = ProviderManager()

