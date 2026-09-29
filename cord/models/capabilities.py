"""
CORD Models - Capability System
Defines capabilities for AI models (chat, streaming, vision, tools, json, reasoning)
and verifies them before execution.
"""

from __future__ import annotations
from enum import Enum
from typing import Set, Dict, Any, Optional
from dataclasses import dataclass, field


class Capability(str, Enum):
    CHAT = "chat"
    STREAMING = "streaming"
    VISION = "vision"
    TOOLS = "tools"
    JSON_MODE = "json"
    REASONING = "reasoning"
    AUDIO = "audio"

# Alias for backward/forward compatibility
ModelCapability = Capability


@dataclass
class ModelCapabilities:
    model_name: str
    capabilities: Set[Capability] = field(default_factory=lambda: {Capability.CHAT, Capability.STREAMING})

    def supports(self, cap: Capability) -> bool:
        return cap in self.capabilities

    def require(self, cap: Capability) -> None:
        if not self.supports(cap):
            raise CapabilityUnsupportedError(
                f"Model '{self.model_name}' does not support required capability: {cap.value}"
            )


class CapabilityUnsupportedError(Exception):
    """Raised when a requested capability is not supported by the selected model."""
    pass


class ModelCapabilityRegistry:
    """Registry to inspect capabilities of various models."""

    def get_capabilities(self, model_name: str) -> Set[Capability]:
        from cord.models.model_resolver import ModelResolver
        return ModelResolver.get_capabilities(model_name).capabilities


model_capability_registry = ModelCapabilityRegistry()
