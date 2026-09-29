"""
Tests for Global Persistent Skills, Subagent Skill Sharing, and Scope Discovery.
Verifies that skills persist globally in ~/.cord/skills/, are loaded across projects,
and can be shared dynamically across subagents in the swarm.
"""

import os
import pytest
from pathlib import Path
from unittest.mock import patch

from cord.tools.skills.create_skill import CreateSkillTool
from cord.tools.skills.improve_skill import ImproveSkillTool
from cord.tools.skills.list_skills import ListSkillsTool
from cord.skills.loader import SkillLoader
from cord.tools.system.swarm_tools import SubagentShareSkillTool
from cord.subagents.message_bus import swarm_bus


@pytest.mark.asyncio
async def test_create_and_load_global_skill(tmp_path, monkeypatch):
    """Verifies that create_skill saves in ~/.cord/skills and SkillLoader discovers it globally."""
    fake_home = tmp_path / "user_home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    tool = CreateSkillTool()
    res = await tool.execute(
        name="test-fastapi-patterns",
        description="Standard FastAPI dependency injection best practices",
        instructions="Always use Depends() for DB session management.",
    )
    assert res.success is True
    assert "global persistent repository" in res.output

    # Check that file actually exists in ~/.cord/skills/
    expected_file = fake_home / ".cord" / "skills" / "test-fastapi-patterns" / "SKILL.md"
    assert expected_file.exists()
    content = expected_file.read_text(encoding="utf-8")
    assert "name: test-fastapi-patterns" in content
    assert "Always use Depends()" in content

    # Test that SkillLoader finds it globally even from a completely different workspace directory
    another_workspace = tmp_path / "unrelated_project"
    another_workspace.mkdir()
    loader = SkillLoader(workspace_path=another_workspace)
    assert "test-fastapi-patterns" in loader.skills
    loaded_skill = loader.skills["test-fastapi-patterns"]
    assert loaded_skill.description == "Standard FastAPI dependency injection best practices"
    assert "Always use Depends()" in loaded_skill.instructions


@pytest.mark.asyncio
async def test_improve_skill_updates_global_file(tmp_path, monkeypatch):
    """Verifies that improve_skill refines the global skill file."""
    fake_home = tmp_path / "user_home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    create_tool = CreateSkillTool()
    await create_tool.execute(
        name="react-state-flow",
        description="React state management rules",
        instructions="Prefer Zustand over Redux for small apps.",
    )

    improve_tool = ImproveSkillTool()
    res = await improve_tool.execute(
        name="react-state-flow",
        new_instructions="Use React Query (TanStack) for server state caching.",
        mode="append",
    )
    assert res.success is True
    assert "saved globally" in res.output

    # Check updated content
    skill_file = fake_home / ".cord" / "skills" / "react-state-flow" / "SKILL.md"
    content = skill_file.read_text(encoding="utf-8")
    assert "Prefer Zustand over Redux" in content
    assert "TanStack" in content


@pytest.mark.asyncio
async def test_list_skills_scope_tagging(tmp_path, monkeypatch):
    """Verifies that list_skills labels [GLOBAL] and [WORKSPACE] scopes."""
    fake_home = tmp_path / "user_home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    create_tool = CreateSkillTool()
    await create_tool.execute(
        name="docker-compose-pro",
        description="Multi-stage docker compose templates",
        instructions="Use compose v2 syntax.",
    )

    list_tool = ListSkillsTool()
    res = await list_tool.execute()
    assert res.success is True
    assert "[GLOBAL]" in res.output
    assert "docker-compose-pro" in res.output


@pytest.mark.asyncio
async def test_subagent_share_skill(tmp_path, monkeypatch):
    """Verifies that subagent_share_skill teaches a skill, persists globally, and broadcasts over message bus."""
    fake_home = tmp_path / "user_home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    swarm_bus.clear()
    swarm_bus.register_agent("coder_1")
    swarm_bus.register_agent("reviewer_1")

    share_tool = SubagentShareSkillTool()
    res = await share_tool.execute(
        name="pytest-mock-async",
        description="Testing async generator endpoints with pytest-asyncio",
        instructions="Use @pytest.mark.asyncio and AsyncMock.",
        recipient_id="*",
        sender_id="coder_1",
    )
    assert res.success is True
    assert "successfully shared" in res.output

    # Verify global disk persistence
    saved_file = fake_home / ".cord" / "skills" / "pytest-mock-async" / "SKILL.md"
    assert saved_file.exists()

    # Verify inbox delivery on reviewer_1
    inbox = swarm_bus.get_inbox("reviewer_1")
    assert len(inbox) >= 1
    assert "pytest-mock-async" in inbox[0]["content"]
