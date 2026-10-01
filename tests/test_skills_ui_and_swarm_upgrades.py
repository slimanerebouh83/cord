"""
Unit tests for CORD Built-in Skills, Enhanced Tool Execution Cards, and Swarm Collaborative Planning.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from cord.skills.loader import SkillLoader, Skill
from cord.ui.renderer import renderer
from cord.ui.console import ui
from cord.tools.base import ToolResult
from cord.subagents.message_bus import swarm_bus


def test_builtin_skills_loading(tmp_path):
    loader = SkillLoader(workspace_path=tmp_path)
    skills = loader.skills
    assert len(skills) >= 7

    assert "calculator" in skills
    assert "desktop-assistant" in skills
    assert "web-automation" in skills
    assert "git-workflow" in skills
    assert "code-refactor" in skills
    assert "test-automator" in skills
    assert "swarm-mesh" in skills

    calc_skill = loader.get_skill("calculator")
    assert calc_skill is not None
    assert "calc.exe" in calc_skill.instructions or "arithmetic" in calc_skill.description.lower()
    assert calc_skill.category != ""


def test_skills_management_and_creation(tmp_path):
    loader = SkillLoader(workspace_path=tmp_path)
    all_skills = loader.list_skills()
    assert len(all_skills) >= 7

    # Create new custom skill
    created_file = loader.create_skill(
        name="custom-ml",
        description="Machine learning workflow instructions",
        instructions="Step 1: Prep data. Step 2: Train model.",
        category="AI & ML",
    )
    assert created_file.exists()
    assert "custom-ml" in loader.skills

    retrieved = loader.get_skill("custom-ml")
    assert retrieved is not None
    assert retrieved.category == "AI & ML"
    assert "Step 1: Prep data" in retrieved.instructions


def test_render_tool_execution_file_system():
    res = ToolResult(success=True, output="Line 1\nLine 2\nLine 3")
    with patch.object(ui.console, "print") as mock_print:
        renderer.render_tool_execution("read_file", {"path": "src/main.py"}, res, elapsed=0.12)
        mock_print.assert_called_once()
        card_str = mock_print.call_args[0][0]
        assert "FILE SYSTEM" in card_str
        assert "Read" in card_str
        assert "src/main.py" in card_str
        assert "120ms" in card_str


def test_render_tool_execution_command():
    res = ToolResult(success=True, output="pytest passed: 100% OK")
    with patch.object(ui.console, "print") as mock_print:
        renderer.render_tool_execution("execute_command", {"command": "pytest"}, res, elapsed=1.45)
        mock_print.assert_called_once()
        card_str = mock_print.call_args[0][0]
        assert "TERMINAL EXECUTION" in card_str
        assert "pytest" in card_str
        assert "1.45s" in card_str


def test_render_tool_execution_desktop_automation():
    res = ToolResult(success=True, output="Mouse moved and clicked at (500, 300)")
    with patch.object(ui.console, "print") as mock_print:
        renderer.render_tool_execution("computer_mouse", {"action": "click", "x": 500, "y": 300}, res, elapsed=0.08)
        mock_print.assert_called_once()
        card_str = mock_print.call_args[0][0]
        assert "DESKTOP AUTOMATION" in card_str
        assert "click" in card_str


def test_render_swarm_collaboration_event():
    with patch.object(ui.console, "print") as mock_print:
        renderer.render_swarm_event(
            event_type="📋 Shared Plan",
            sender="researcher-1",
            recipient="coder-2",
            summary="Refactor auth module steps agreed upon.",
        )
        mock_print.assert_called_once()
        card_str = mock_print.call_args[0][0]
        assert "SWARM COLLABORATION" in card_str
        assert "researcher-1" in card_str
        assert "coder-2" in card_str


def test_swarm_collaborative_planning():
    swarm_bus.clear()
    swarm_bus.register_agent("peer-alpha")
    swarm_bus.register_agent("peer-beta")

    # Publish plan
    plan = swarm_bus.publish_plan(
        author_id="peer-alpha",
        title="Database Migration",
        steps=["Backup DB", "Run Alembic", "Verify integrity"],
    )
    assert plan["id"].startswith("plan-")
    assert plan["author"] == "peer-alpha"
    assert len(plan["steps"]) == 3

    # Check peer inbox received plan broadcast
    beta_inbox = swarm_bus.get_inbox("peer-beta")
    assert len(beta_inbox) >= 1
    assert "Database Migration" in beta_inbox[0]["content"]

    # Vote on plan
    voted = swarm_bus.vote_on_plan(voter_id="peer-beta", plan_id=plan["id"], approve=True, comment="LGTM!")
    assert voted is True
    assert plan["votes"]["peer-beta"] is True

    # Share finding
    finding = swarm_bus.share_finding(author_id="peer-beta", topic="Postgres 16", finding="Index optimization improves query 40%")
    assert finding["author"] == "peer-beta"
    assert len(swarm_bus.get_findings()) == 1


def test_console_banner_with_skills_and_swarm():
    with patch.object(ui.console, "print") as mock_print:
        ui.print_banner(
            model="gemini-2.5-flash",
            provider="google",
            mode="yolo",
            skills_count=12,
            swarm_active=True,
        )
        mock_print.assert_called_once()
        panel_arg = mock_print.call_args[0][0]
        text_content = panel_arg.renderable.plain
        assert "Autonomous Terminal Coding Agent" in text_content
        assert "gemini-2.5-flash" in text_content
        assert "GOOGLE" in text_content
        assert "YOLO" in text_content
        assert "12 Active" in text_content
        assert "10k+ Mesh Ready" in text_content
