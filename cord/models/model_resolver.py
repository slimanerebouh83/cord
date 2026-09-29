"""
CORD Models - Dynamic Model Resolver
Parses model strings, verifies capabilities, and selects dynamic fallbacks.
"""

from __future__ import annotations
import re
from typing import Tuple, Optional, List, Dict, Any, Set
from cord.models.capabilities import Capability, ModelCapabilities, CapabilityUnsupportedError


class ModelResolver:
    """Dynamically resolves model identifiers, providers, and capabilities."""

    PROVIDER_PREFIXES = {
        "openai", "anthropic", "gemini", "groq", "deepseek",
        "mistral", "xai", "together_ai", "openrouter", "ollama",
        "azure", "bedrock", "vertex_ai", "cohere", "huggingface"
    }

    @classmethod
    def parse_model(cls, model_identifier: str) -> Tuple[Optional[str], str]:
        """
        Parses 'provider/model_name' into (provider, model_name).
        Examples:
          'groq/openai/gpt-oss-120b' -> ('groq', 'openai/gpt-oss-120b')
          'anthropic/claude-3-7-sonnet' -> ('anthropic', 'claude-3-7-sonnet')
          'gpt-4o' -> ('openai', 'gpt-4o')
        """
        if not model_identifier:
            return None, "gpt-4o"

        parts = model_identifier.split("/", 1)
        if len(parts) == 2 and parts[0].lower() in cls.PROVIDER_PREFIXES:
            return parts[0].lower(), parts[1]

        # Automatic detection heuristic based on naming conventions
        name_lower = model_identifier.lower()
        if "claude" in name_lower:
            return "anthropic", model_identifier
        elif "gpt" in name_lower or name_lower.startswith("o1") or name_lower.startswith("o3"):
            return "openai", model_identifier
        elif "gemini" in name_lower:
            return "gemini", model_identifier
        elif "deepseek" in name_lower:
            return "deepseek", model_identifier
        elif "grok" in name_lower:
            return "xai", model_identifier
        elif "codestral" in name_lower or "mistral" in name_lower:
            return "mistral", model_identifier
        elif "qwen" in name_lower or "llama" in name_lower:
            return "openrouter", model_identifier

        return None, model_identifier

    @classmethod
    def get_capabilities(cls, model_name: str) -> ModelCapabilities:
        """Determines model capabilities based on model properties."""
        caps: Set[Capability] = {Capability.CHAT, Capability.STREAMING, Capability.TOOLS, Capability.JSON_MODE}
        name_lower = model_name.lower()

        # Reasoning capability
        if any(r in name_lower for r in ("r1", "reasoner", "o1", "o3", "thinking")):
            caps.add(Capability.REASONING)

        # Vision capability
        if any(v in name_lower for v in ("vision", "4o", "gemini", "grok-2-vision", "claude-3")):
            caps.add(Capability.VISION)

        return ModelCapabilities(model_name=model_name, capabilities=caps)

    @classmethod
    def get_fallback_model(cls, failed_model: str, provider: Optional[str] = None) -> Optional[str]:
        """
        Picks a sensible fallback model when a model fails or is decommissioned.
        """
        prov = provider or cls.parse_model(failed_model)[0]

        if prov == "groq":
            return "openai/gpt-oss-120b"
        elif prov == "openai":
            return "gpt-4o-mini"
        elif prov == "anthropic":
            return "claude-3-5-haiku-20241022"
        elif prov == "gemini":
            return "gemini-2.0-flash"
        elif prov == "deepseek":
            return "deepseek-chat"
        elif prov == "openrouter":
            return "anthropic/claude-3.7-sonnet"
        elif prov == "nvidia" or "nvidia" in failed_model.lower():
            return "nvidia/nemotron-3-super-120b-a12b"
        elif prov == "moonshot" or "kimi" in failed_model.lower():
            return "moonshot-v1-8k"
        elif prov == "together":
            return "meta-llama/Llama-3.3-70B-Instruct-Turbo"

        return "gpt-4o-mini"


model_resolver = ModelResolver()

