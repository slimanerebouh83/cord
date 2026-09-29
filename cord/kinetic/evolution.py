"""
KINETIC-CORE: Self-Evolving & Adaptive Optimization Engine.
Continuously mutates execution parameters, compiles repetitive action chains into 0ms reflexes,
and auto-tunes application latency profiles to hardware limits.
Persisted in ~/.cord/kinetic_evolution.json.
"""

from __future__ import annotations
import json
import os
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict


@dataclass
class AppLatencyProfile:
    app_name: str
    typing_delay_ms: float = 2.0
    click_debounce_ms: float = 2.0
    focus_delay_ms: float = 15.0
    success_count: int = 0
    failure_count: int = 0
    min_latency_achieved: float = 2.0
    updated_at: float = field(default_factory=time.time)

    def optimize_success(self) -> None:
        self.success_count += 1
        # Auto-tune: decrease latency toward zero if reliable
        if self.success_count % 3 == 0:
            self.typing_delay_ms = max(0.2, self.typing_delay_ms * 0.85)
            self.click_debounce_ms = max(0.5, self.click_debounce_ms * 0.85)
            self.focus_delay_ms = max(5.0, self.focus_delay_ms * 0.90)
            self.min_latency_achieved = min(self.min_latency_achieved, self.typing_delay_ms)
        self.updated_at = time.time()

    def penalize_failure(self) -> None:
        self.failure_count += 1
        # Back off to maintain stability
        self.typing_delay_ms = min(20.0, self.typing_delay_ms * 1.4)
        self.click_debounce_ms = min(15.0, self.click_debounce_ms * 1.3)
        self.focus_delay_ms = min(50.0, self.focus_delay_ms * 1.3)
        self.updated_at = time.time()


@dataclass
class ReflexMacro:
    name: str
    intent: str
    actions: List[Dict[str, Any]]
    execution_count: int = 0
    avg_latency_ms: float = 0.0
    created_at: float = field(default_factory=time.time)


class KineticEvolution:
    """Oversees autonomous self-evolution, latency adaptation, and reflex synthesis."""

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or (Path.home() / ".cord" / "kinetic_evolution.json")
        self.profiles: Dict[str, AppLatencyProfile] = {}
        self.reflexes: Dict[str, ReflexMacro] = {}
        self.generation: int = 1
        self.total_actions_dispatched: int = 0
        self.total_time_saved_sec: float = 0.0
        self._load()

    def _load(self) -> None:
        try:
            if self.storage_path.exists():
                data = json.loads(self.storage_path.read_text(encoding="utf-8"))
                self.generation = data.get("generation", 1)
                self.total_actions_dispatched = data.get("total_actions_dispatched", 0)
                self.total_time_saved_sec = data.get("total_time_saved_sec", 0.0)

                for name, p_data in data.get("profiles", {}).items():
                    self.profiles[name] = AppLatencyProfile(**p_data)

                for name, r_data in data.get("reflexes", {}).items():
                    self.reflexes[name] = ReflexMacro(**r_data)
        except Exception:
            pass

    def save(self) -> None:
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            export_data = {
                "generation": self.generation,
                "total_actions_dispatched": self.total_actions_dispatched,
                "total_time_saved_sec": round(self.total_time_saved_sec, 2),
                "profiles": {k: asdict(v) for k, v in self.profiles.items()},
                "reflexes": {k: asdict(v) for k, v in self.reflexes.items()},
                "updated_at": time.time(),
            }
            self.storage_path.write_text(json.dumps(export_data, indent=2), encoding="utf-8")
        except Exception:
            pass

    def get_profile(self, app_name: str = "default") -> AppLatencyProfile:
        key = (app_name or "default").lower().strip()
        if key not in self.profiles:
            self.profiles[key] = AppLatencyProfile(app_name=key)
        return self.profiles[key]

    def record_action_batch(self, app_name: str, action_count: int, elapsed_ms: float, success: bool) -> None:
        """Records execution telemetry, triggering self-evolution and parameter adaptation."""
        self.total_actions_dispatched += action_count
        prof = self.get_profile(app_name)

        if success:
            prof.optimize_success()
            # Saved time vs roundtrip (approx 2500ms per action in conventional LLM tool roundtrip)
            conventional_ms = action_count * 2500.0
            self.total_time_saved_sec += max(0.0, (conventional_ms - elapsed_ms) / 1000.0)
        else:
            prof.penalize_failure()

        if self.total_actions_dispatched % 50 == 0:
            self.generation += 1

        self.save()

    def register_reflex(self, name: str, intent: str, actions: List[Dict[str, Any]]) -> ReflexMacro:
        """Registers or updates a synthesized reflex macro."""
        reflex = ReflexMacro(
            name=name.strip().lower(),
            intent=intent.strip(),
            actions=actions,
        )
        self.reflexes[reflex.name] = reflex
        self.save()
        return reflex

    def get_reflex(self, name_or_intent: str) -> Optional[ReflexMacro]:
        query = name_or_intent.strip().lower()
        if query in self.reflexes:
            return self.reflexes[query]
        for r in self.reflexes.values():
            if query in r.intent.lower() or r.name in query:
                return r
        return None

    def get_stats(self) -> Dict[str, Any]:
        return {
            "generation": self.generation,
            "total_actions_dispatched": self.total_actions_dispatched,
            "total_time_saved_sec": round(self.total_time_saved_sec, 2),
            "total_profiles": len(self.profiles),
            "total_reflexes": len(self.reflexes),
            "profiles": {
                k: {
                    "typing_delay_ms": round(v.typing_delay_ms, 2),
                    "click_debounce_ms": round(v.click_debounce_ms, 2),
                    "success_count": v.success_count,
                    "failure_count": v.failure_count,
                    "min_latency_achieved": round(v.min_latency_achieved, 2),
                }
                for k, v in self.profiles.items()
            },
            "reflexes": [
                {
                    "name": r.name,
                    "intent": r.intent,
                    "steps": len(r.actions),
                    "execution_count": r.execution_count,
                    "avg_latency_ms": round(r.avg_latency_ms, 2),
                }
                for r in self.reflexes.values()
            ],
        }


kinetic_evolution = KineticEvolution()
