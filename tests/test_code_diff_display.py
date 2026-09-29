"""Tests for Code Diff Display, AI Cursor HUD, and Autonomous Visual Testing"""
import pytest
from pathlib import Path
from cord.tools.filesystem.write_file import WriteFileTool
from cord.tools.filesystem.edit_file import EditFileTool
from cord.ui.renderer import ChatRenderer
from cord.core.modes import MODE_PROFILES, OperationalMode
from cord.tools.project.run_project import RunProjectTool


@pytest.mark.asyncio
async def test_write_file_metadata_and_line_deltas(tmp_path):
    target = tmp_path / "script.py"
    writer = WriteFileTool()
    
    # 1. Create file
    content1 = "def foo():\n    return 1\n"
    res1 = await writer.execute(path=str(target), content=content1)
    assert res1.success is True
    assert res1.metadata["lines_added"] == 2
    assert res1.metadata["lines_removed"] == 0
    assert res1.metadata["action"] == "created"
    assert "+2 lines" in res1.output

    # 2. Overwrite file with more lines
    content2 = "def foo():\n    x = 10\n    y = 20\n    return x + y\n"
    res2 = await writer.execute(path=str(target), content=content2)
    assert res2.success is True
    assert res2.metadata["lines_added"] == 2
    assert res2.metadata["action"] == "overwrote"


@pytest.mark.asyncio
async def test_edit_file_metadata_and_line_deltas(tmp_path):
    target = tmp_path / "main.py"
    target.write_text("line 1\nline 2\nline 3\nline 4\n", encoding="utf-8")
    
    editor = EditFileTool()
    res = await editor.execute(
        path=str(target),
        old_content="line 2\nline 3",
        new_content="line 2 - modified\nline 2.5 - added\nline 3 - modified\nline 3.5 - added"
    )
    assert res.success is True
    assert res.metadata["lines_added"] >= 2
    assert res.metadata["filename"] == "main.py"
    assert "diff" in res.metadata


def test_renderer_code_card():
    from cord.tools.base import ToolResult
    res = ToolResult(
        success=True,
        output="Updated test.py",
        metadata={
            "filename": "test.py",
            "lines_added": 5,
            "lines_removed": 2,
            "diff": "@@ -1,2 +1,5 @@\n-old line\n+new line 1\n+new line 2",
            "snippet": "print('hello')"
        }
    )
    # Ensure it renders without exception
    ChatRenderer.render_tool_execution(
        tool_name="edit_file",
        args={"path": "test.py"},
        result=res,
        elapsed_sec=0.045
    )


def test_coder_mode_computer_tools_and_visual_testing():
    coder = MODE_PROFILES[OperationalMode.CODER]
    assert "computer_act" in coder.tool_filter
    assert "computer_screenshot" in coder.tool_filter
    assert "browser_media" in coder.tool_filter
    assert "AUTONOMOUS VISUAL PROJECT TESTING" in coder.system_prompt_addon


@pytest.mark.asyncio
async def test_run_project_visual_testing_guide(monkeypatch):
    tool = RunProjectTool()
    monkeypatch.setattr("subprocess.Popen", lambda *a, **kw: type("Proc", (), {"pid": 12345, "stdout": None, "stderr": None})())
    res = await tool.execute(command="npm run dev", background=True)
    assert res.success is True
    assert "Computer-Use Autonomous Testing Guide" in res.output
    assert "browser_media" in res.output
    assert "computer_screenshot" in res.output
