"""
NITEE v3 - Skill Compiler Module
Compiles successful, clean batch execution plans into reusable deterministic skills.
Enables zero-LLM replay for recurring workflows.
"""

from __future__ import annotations
import re
import json
import time
from pathlib import Path
from typing import Dict, List, Any, Optional


class SkillCompiler:
    """Compiles successful plan batches into deterministic zero-LLM skills."""

    def __init__(self, storage_dir: Optional[Path] = None):
        if storage_dir is None:
            self.storage_dir = Path.home() / ".cord" / "compiled_skills"
        else:
            self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _sanitize_name(self, goal: str) -> str:
        """Derive a valid file/skill identifier from a goal description."""
        clean = re.sub(r"[^a-zA-Z0-9_\s]", "", goal.lower())
        tokens = clean.strip().split()
        return "_".join(tokens[:5]) or "unnamed_skill"

    def compile(
        self,
        goal: str,
        plan: List[Dict[str, Any]],
        summary: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Compile a clean execution batch into a reusable skill artifact.
        
        Args:
            goal: User goal
            plan: The sequence of plan actions that succeeded
            summary: One-line progress note / completion summary
            metadata: Additional execution context
            
        Returns:
            Dict representing the compiled skill
        """
        skill_name = self._sanitize_name(goal)
        file_path = self.storage_dir / f"{skill_name}.json"

        # Filter and clean executable plan steps (strip volatile dynamic IDs if needed, preserve labels)
        clean_steps = []
        for step in plan:
            action = step.get("action", "").upper()
            if action == "DONE":
                continue
            clean_steps.append({
                "step": len(clean_steps) + 1,
                "action": action,
                "element_id": step.get("element_id"),
                "value": step.get("value"),
                "wait_label": step.get("wait_label"),
                "expect": step.get("expect"),
                "risk": step.get("risk", "low"),
            })

        skill_data = {
            "name": skill_name,
            "goal": goal,
            "summary": summary,
            "compiled_at": time.time(),
            "step_count": len(clean_steps),
            "steps": clean_steps,
            "metadata": metadata or {},
            "replay_count": 0,
        }

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(skill_data, f, indent=2)
        except Exception:
            pass

        return skill_data

    def load_skill(self, skill_name: str) -> Optional[Dict[str, Any]]:
        """Load a compiled skill by name."""
        clean = self._sanitize_name(skill_name)
        file_path = self.storage_dir / f"{clean}.json"
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return None
        return None

    def list_skills(self) -> List[Dict[str, Any]]:
        """List all compiled deterministic skills."""
        results = []
        if not self.storage_dir.exists():
            return results

        for f in self.storage_dir.glob("*.json"):
            try:
                with open(f, "r", encoding="utf-8") as file:
                    data = json.load(file)
                    results.append({
                        "name": data.get("name"),
                        "goal": data.get("goal"),
                        "steps": len(data.get("steps", [])),
                        "compiled_at": data.get("compiled_at"),
                    })
            except Exception:
                continue
        return results
