"""
Tests for Planner, Skills Loader, and Subagents.
"""

import pytest
from pathlib import Path
from cord.core.planner import PlanManager
from cord.skills.loader import SkillLoader
from cord.subagents.roles import ROLE_CONFIGS


def test_plan_manager():
    mgr = PlanManager()
    plan = mgr.create_plan(
        goal="Refactor authentication",
        step_titles=["Add JWT parser", "Add token validation", "Write tests"],
    )
    assert len(plan.steps) == 3
    assert plan.steps[0].status == "pending"

    # Update step
    updated = mgr.update_step(1, "in_progress", "Started parser implementation")
    assert updated.status == "in_progress"
    assert updated.notes == "Started parser implementation"

    updated = mgr.update_step(1, "completed", "Done parser")
    assert updated.status == "completed"


def test_skills_loader(tmp_path):
    skills_dir = tmp_path / ".cord" / "skills" / "docker-helper"
    skills_dir.mkdir(parents=True)
    skill_file = skills_dir / "SKILL.md"
    skill_file.write_text(
        "---\nname: docker-helper\ndescription: Helps write Dockerfiles\n---\nUse multi-stage builds.\n",
        encoding="utf-8",
    )

    loader = SkillLoader(workspace_path=tmp_path)
    assert "docker-helper" in loader.skills
    assert loader.skills["docker-helper"].description == "Helps write Dockerfiles"
    prompt_text = loader.format_skills_for_prompt()
    assert "### Skill: `docker-helper`" in prompt_text


def test_subagents_role_definitions():
    assert "researcher" in ROLE_CONFIGS
    assert "coder" in ROLE_CONFIGS
    assert "reviewer" in ROLE_CONFIGS
    assert "tester" in ROLE_CONFIGS

    # Researcher must be read-only
    assert "write_file" not in ROLE_CONFIGS["researcher"]["allowed_tools"]
    assert "read_file" in ROLE_CONFIGS["researcher"]["allowed_tools"]

    # Coder can write and edit
    assert "write_file" in ROLE_CONFIGS["coder"]["allowed_tools"]
    assert "edit_file" in ROLE_CONFIGS["coder"]["allowed_tools"]
