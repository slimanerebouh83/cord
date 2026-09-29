"""
KINETIC-CORE: Reflex Engine.
Compiles high-level intents into instantaneous local reflex chains, bypassing LLM roundtrips entirely.
"""

from __future__ import annotations
import time
from typing import List, Dict, Any, Optional
from cord.kinetic.evolution import kinetic_evolution, ReflexMacro


BUILTIN_REFLEXES = {
    "save": {"intent": "save active file or document", "actions": [{"action": "hotkey", "hotkey": "ctrl+s"}]},
    "copy": {"intent": "copy selected text to clipboard", "actions": [{"action": "hotkey", "hotkey": "ctrl+c"}]},
    "paste": {"intent": "paste clipboard content", "actions": [{"action": "hotkey", "hotkey": "ctrl+v"}]},
    "select_all": {"intent": "select all text in focus", "actions": [{"action": "hotkey", "hotkey": "ctrl+a"}]},
    "undo": {"intent": "undo last operation", "actions": [{"action": "hotkey", "hotkey": "ctrl+z"}]},
    "new_tab": {"intent": "open new browser or editor tab", "actions": [{"action": "hotkey", "hotkey": "ctrl+t"}]},
    "close_tab": {"intent": "close active tab", "actions": [{"action": "hotkey", "hotkey": "ctrl+w"}]},
    "switch_app": {"intent": "switch to next active application", "actions": [{"action": "hotkey", "hotkey": "alt+tab"}]},
    "open_run": {"intent": "open Windows Run dialog", "actions": [{"action": "hotkey", "hotkey": "win+r"}]},
    "find": {"intent": "open search in document", "actions": [{"action": "hotkey", "hotkey": "ctrl+f"}]},
}


class KineticReflexEngine:
    """Dispatches pre-compiled and self-evolved reflex macros with zero LLM reasoning latency."""

    def __init__(self):
        self._ensure_builtins()

    def _ensure_builtins(self) -> None:
        for name, data in BUILTIN_REFLEXES.items():
            if not kinetic_evolution.get_reflex(name):
                kinetic_evolution.register_reflex(name, data["intent"], data["actions"])

    def resolve(self, query: str) -> Optional[ReflexMacro]:
        """Resolves natural language or shortcut name into a compiled reflex."""
        clean = query.strip().lower()
        if clean.startswith("reflex:"):
            clean = clean[7:].strip()
        return kinetic_evolution.get_reflex(clean)

    def learn_chain(self, name: str, intent: str, actions: List[Dict[str, Any]]) -> ReflexMacro:
        """Dynamically learns and stores a new macro sequence from execution history."""
        return kinetic_evolution.register_reflex(name, intent, actions)


kinetic_reflex = KineticReflexEngine()
