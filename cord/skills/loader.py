"""
CORD Skills - Modular Extensibility System
Discovers, parses, and injects custom skills from .cord/skills/ and ~/.cord/skills/.
"""

from __future__ import annotations
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from cord.ui.console import ui


@dataclass
class Skill:
    name: str
    description: str
    instructions: str
    path: Path


class SkillLoader:
    """Discovers and manages custom skills."""

    def __init__(self, workspace_path: Optional[Path] = None):
        self.workspace_path = workspace_path or Path.cwd()
        self.skills: Dict[str, Skill] = {}
        self.reload()

    def get_search_paths(self) -> List[Path]:
        return [
            Path.home() / ".cord" / "skills",
            self.workspace_path / ".cord" / "skills",
        ]

    def reload(self) -> None:
        self.skills.clear()
        for folder in self.get_search_paths():
            if not folder.exists() or not folder.is_dir():
                continue
            for item in folder.iterdir():
                if item.is_dir():
                    skill_md = item / "SKILL.md"
                    if skill_md.exists():
                        self._parse_skill_file(skill_md, default_name=item.name)
                elif item.is_file() and item.suffix == ".md":
                    self._parse_skill_file(item, default_name=item.stem)

    def _parse_skill_file(self, path: Path, default_name: str) -> None:
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            # Parse YAML frontmatter if present:
            # ---
            # name: my-skill
            # description: Does xyz
            # ---
            name = default_name
            description = ""
            instructions = content

            frontmatter_match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
            if frontmatter_match:
                fm_text = frontmatter_match.group(1)
                instructions = frontmatter_match.group(2)
                for line in fm_text.splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        k = k.strip().lower()
                        v = v.strip().strip("\"'")
                        if k == "name":
                            name = v
                        elif k == "description":
                            description = v

            if not description:
                # Use first non-empty line as description
                first_lines = [l.strip() for l in instructions.splitlines() if l.strip() and not l.startswith("#")]
                description = first_lines[0][:100] if first_lines else "Custom skill"

            self.skills[name] = Skill(
                name=name,
                description=description,
                instructions=instructions.strip(),
                path=path,
            )
        except Exception as e:
            ui.print_warning(f"Failed to load skill from {path}: {e}")

    def format_skills_for_prompt(self) -> str:
        """Formats loaded skills into system prompt context."""
        if not self.skills:
            return ""

        parts = ["\nAvailable Specialized Skills:\n"]
        for s in self.skills.values():
            parts.append(f"### Skill: `{s.name}`\n**Description**: {s.description}\n**Instructions**:\n{s.instructions}\n")
        return "\n".join(parts)
