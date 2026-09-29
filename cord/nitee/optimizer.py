"""
NITEE v3 - Optimizer Module
Self-Optimizing Wait Duration Manager.
Learns real elapsed wait durations and persists them to ~/.cord/optimizer.json.
"""

from __future__ import annotations
import json
import os
import time
from pathlib import Path
from typing import Dict, Any, Optional


class WaitOptimizer:
    """Tracks, measures, and converges on real wait durations for labeled states."""

    def __init__(self, storage_path: Optional[Path] = None):
        if storage_path is None:
            home = Path.home()
            cord_dir = home / ".cord"
            cord_dir.mkdir(parents=True, exist_ok=True)
            self.storage_path = cord_dir / "optimizer.json"
        else:
            self.storage_path = Path(storage_path)
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        self._stats: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self._stats = data
            except Exception:
                self._stats = {}

    def _save(self) -> None:
        try:
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(self._stats, f, indent=2)
        except Exception:
            pass

    def record_wait(self, label: str, duration_ms: float) -> Dict[str, Any]:
        """Record a measured wait duration in milliseconds for a label."""
        if not label:
            return {}

        clean_label = str(label).strip().lower()
        duration_ms = max(0.0, float(duration_ms))

        if clean_label in self._stats:
            entry = self._stats[clean_label]
            samples = int(entry.get("samples", 0)) + 1
            prev_avg = float(entry.get("avg_ms", duration_ms))
            # Exponential moving average with increasing weight for samples
            alpha = 1.0 / min(samples, 10)
            new_avg = round((1.0 - alpha) * prev_avg + alpha * duration_ms, 2)
            entry["avg_ms"] = new_avg
            entry["samples"] = samples
            entry["last_ms"] = round(duration_ms, 2)
            entry["updated_at"] = time.time()
        else:
            self._stats[clean_label] = {
                "avg_ms": round(duration_ms, 2),
                "samples": 1,
                "last_ms": round(duration_ms, 2),
                "created_at": time.time(),
                "updated_at": time.time(),
            }

        self._save()
        return self._stats[clean_label]

    def get_learned_wait(self, label: str, default_ms: float = 500.0) -> float:
        """Get the predicted wait duration in milliseconds for a label."""
        clean_label = str(label).strip().lower()
        if clean_label in self._stats:
            return float(self._stats[clean_label].get("avg_ms", default_ms))
        return float(default_ms)

    def get_stats(self) -> Dict[str, Any]:
        """Return snapshot of learned wait durations for NITEE prompt context."""
        return {
            label: {
                "avg_ms": data.get("avg_ms", 0.0),
                "samples": data.get("samples", 0),
                "last_ms": data.get("last_ms", 0.0),
            }
            for label, data in self._stats.items()
        }

    def clear(self) -> None:
        """Reset all optimizer statistics."""
        self._stats = {}
        self._save()
