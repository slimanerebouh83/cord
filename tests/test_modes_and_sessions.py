"""Tests for CORD Modes, Session History, Arabic Reshaping, Skills Tools, and Statistics."""
import pytest
import os
import shutil
from pathlib import Path

from cord.core.modes import OperationalMode, ModeManager, MODE_PROFILES
from cord.memory.sessions import SessionManager
from cord.ui.arabic import is_arabic, fix_arabic
from cord.tools.skills.create_skill import CreateSkillTool
from cord.tools.skills.improve_skill import ImproveSkillTool
from cord.tools.skills.list_skills import ListSkillsTool
from cord.ui.stats_panel import get_workspace_file_stats, get_git_info


def test_modes_and_profiles():
    manager = ModeManager(OperationalMode.AGENT)
    assert manager.current_mode == OperationalMode.AGENT
    profile = manager.get_profile()
    assert profile.name == "Agent"
    assert "AGENT FIRST" in profile.system_prompt_addon

    # Switch to fast
    p_fast = manager.set_mode("fast")
    assert p_fast is not None
    assert p_fast.id == OperationalMode.FAST
    assert p_fast.temperature == 0.3

    # Switch using alias
    p_comp = manager.set_mode("كمبيوتر")
    assert p_comp is not None
    assert p_comp.id == OperationalMode.COMPUTER
    assert "NITEE v3" in p_comp.system_prompt_addon

    # Switch to coder
    p_coder = manager.set_mode("coder")
    assert p_coder is not None
    assert p_coder.id == OperationalMode.CODER
    assert p_coder.auto_verify is True

    # Invalid mode
    assert manager.set_mode("nonexistent_mode") is None


def test_session_manager(tmp_path):
    sm = SessionManager(sessions_dir=tmp_path)
    messages = [
        {"role": "user", "content": "مرحبا، أريد كتابة كود بايثون"},
        {"role": "assistant", "content": "أهلاً بك! كيف يمكنني مساعدتك؟"},
    ]

    saved_path = sm.save_session(
        messages=messages,
        model="nvidia/llama-3.1-nemotron-70b-instruct",
        mode="coder",
        session_id="test_session_01"
    )
    assert saved_path.exists()

    # List sessions
    sessions = sm.list_sessions()
    assert len(sessions) == 1
    assert sessions[0]["id"] == "test_session_01"
    assert "مرحبا" in sessions[0]["title"]
    assert sessions[0]["message_count"] == 2
    assert sessions[0]["mode"] == "coder"

    # Load session
    loaded = sm.load_session("test_session_01")
    assert loaded is not None
    assert len(loaded["messages"]) == 2
    assert loaded["messages"][0]["content"] == "مرحبا، أريد كتابة كود بايثون"

    # Delete session
    assert sm.delete_session("test_session_01") is True
    assert len(sm.list_sessions()) == 0
    assert sm.load_session("test_session_01") is None


def test_arabic_reshaping():
    # Pass-through ensures stability without unwanted transformations
    english = "Hello from CORD"
    assert fix_arabic(english) == english
    assert is_arabic("Hello World") is False


@pytest.mark.asyncio
async def test_skills_tools(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    create_tool = CreateSkillTool()
    improve_tool = ImproveSkillTool()
    list_tool = ListSkillsTool()

    # 1. Create a skill
    res = await create_tool.execute(
        name="pytest-guide",
        description="Best practices for writing fast pytest tests",
        instructions="Always use tmp_path and avoid hardcoded absolute paths."
    )
    assert res.success is True
    skill_file = tmp_path / ".cord" / "skills" / "pytest-guide" / "SKILL.md"
    assert skill_file.exists()
    content = skill_file.read_text(encoding="utf-8")
    assert "pytest-guide" in content
    assert "tmp_path" in content

    # 2. List skills
    list_res = await list_tool.execute()
    assert list_res.success is True
    assert "pytest-guide" in list_res.output

    # 3. Improve skill (append)
    imp_res = await improve_tool.execute(
        name="pytest-guide",
        new_instructions="Also use mock fixtures for network calls.",
        mode="append"
    )
    assert imp_res.success is True
    updated_content = skill_file.read_text(encoding="utf-8")
    assert "mock fixtures" in updated_content
    assert "tmp_path" in updated_content


def test_workspace_stats(tmp_path):
    # Create sample files
    f1 = tmp_path / "main.py"
    f1.write_text("print('hello')\nx = 1\n", encoding="utf-8")

    f2 = tmp_path / "README.md"
    f2.write_text("# Readme\nTest doc\nLine 3\n", encoding="utf-8")

    stats = get_workspace_file_stats(tmp_path)
    assert stats["total_files"] == 2
    assert stats["code_files"] == 2
    assert stats["total_loc"] == 5

    branch, changed = get_git_info(tmp_path)
    assert isinstance(branch, str)
    assert isinstance(changed, int)
