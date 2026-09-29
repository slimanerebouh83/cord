"""
Tests for CORD enhancements:
- Continuous thinking & ThoughtStreamFilter tag extraction
- Surgical EditFileTool line operations (line replacement, line deletion, line insertion, fuzzy whitespace)
- File-scoped conversation sessions & changelog tracking
- Changes dashboard & Tool inspector
"""

import pytest
from pathlib import Path
from cord.core.llm import ThoughtStreamFilter
from cord.tools.filesystem.edit_file import EditFileTool
from cord.memory.sessions import SessionManager
from cord.ui.changes_dashboard import render_changes_dashboard
from cord.ui.tool_inspector import ToolInspector


def test_thought_stream_filter_basic():
    filt = ThoughtStreamFilter()
    out = filt.process("Hello <thought>Let me think about this</thought>World")
    assert ("text", "Hello ") in out
    assert ("thinking", "Let me think about this") in out
    assert ("text", "World") in out


def test_thought_stream_filter_streaming_chunks():
    filt = ThoughtStreamFilter()
    c1 = filt.process("<thought>Analyzing")
    assert ("thinking", "Analyzing") in c1

    c2 = filt.process(" the codebase deeply</thought>Here is")
    assert ("thinking", " the codebase deeply") in c2
    assert ("text", "Here is") in c2

    c3 = filt.process(" the answer.")
    assert ("text", " the answer.") in c3


def test_thought_stream_filter_interleaved():
    filt = ThoughtStreamFilter()
    res = filt.process("<thought>Step 1</thought>Code 1<thought>Step 2</thought>Code 2")
    kinds = [k for k, _ in res]
    assert kinds == ["thinking", "text", "thinking", "text"]


@pytest.mark.asyncio
async def test_edit_file_line_range(tmp_path):
    f = tmp_path / "sample.py"
    f.write_text("line 1\nline 2\nline 3\nline 4\nline 5\n", encoding="utf-8")

    tool = EditFileTool()
    # Replace lines 2 to 3
    res = await tool.execute(path=str(f), start_line=2, end_line=3, new_content="replaced content")
    assert res.success is True
    content = f.read_text(encoding="utf-8")
    assert "replaced content" in content
    assert "line 2" not in content
    assert "line 3" not in content
    assert "line 1" in content
    assert "line 4" in content


@pytest.mark.asyncio
async def test_edit_file_line_deletion(tmp_path):
    f = tmp_path / "sample_del.py"
    f.write_text("line A\nline B\nline C\nline D\n", encoding="utf-8")

    tool = EditFileTool()
    # Delete line 2 (line B) by passing new_content=""
    res = await tool.execute(path=str(f), start_line=2, end_line=2, new_content="")
    assert res.success is True
    content = f.read_text(encoding="utf-8")
    assert "line B" not in content
    assert "line A\nline C\nline D" in content


@pytest.mark.asyncio
async def test_edit_file_insertion(tmp_path):
    f = tmp_path / "sample_ins.py"
    f.write_text("first\nsecond\n", encoding="utf-8")

    tool = EditFileTool()
    # Insert after line 1
    res = await tool.execute(path=str(f), insert_after_line=1, new_content="inserted line")
    assert res.success is True
    lines = f.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "first"
    assert lines[1] == "inserted line"
    assert lines[2] == "second"


@pytest.mark.asyncio
async def test_edit_file_fuzzy_whitespace(tmp_path):
    f = tmp_path / "sample_fuzzy.py"
    f.write_text("def hello():\n    print('hi')  \n", encoding="utf-8")

    tool = EditFileTool()
    # Search with different trailing whitespace
    res = await tool.execute(path=str(f), old_content="def hello():\n  print('hi')", new_content="def hello():\n    print('hello world')")
    assert res.success is True
    assert "hello world" in f.read_text(encoding="utf-8")


def test_session_manager_file_scoping_and_changes(tmp_path):
    sm = SessionManager(sessions_dir=tmp_path / "sessions")
    sid = sm.get_new_session_id(target_file="app.py")
    assert sm.current_target_file == "app.py"

    sm.record_session_change(
        file_path="app.py",
        action="edited",
        diff="+new line",
        lines_added=1,
        lines_removed=0,
        description="test edit"
    )

    changes = sm.get_session_changes()
    assert len(changes) == 1
    assert changes[0]["file"] == "app.py"

    sm.save_session(messages=[{"role": "user", "content": "Update app"}])
    
    # List filtered by target_file
    scoped_sessions = sm.list_sessions(target_file="app.py")
    assert len(scoped_sessions) == 1
    assert scoped_sessions[0]["target_file"] == "app.py"
    assert scoped_sessions[0]["lines_added"] == 1

    # Filter for non-matching file
    other_sessions = sm.list_sessions(target_file="other.py")
    assert len(other_sessions) == 0


def test_changes_dashboard_rendering(tmp_path):
    sm = SessionManager(sessions_dir=tmp_path / "sessions")
    sm.record_session_change(
        file_path="main.py",
        action="edited",
        diff="+line1\n-line0",
        lines_added=1,
        lines_removed=1,
    )
    # Ensure no exceptions during render
    render_changes_dashboard()


def test_tool_inspector_instantiation():
    history = [{
        "name": "edit_file",
        "args": {"path": "app.py", "new_content": "print('ok')"},
        "result": None,
        "elapsed": 0.015,
        "timestamp": 123456.0,
    }]
    inspector = ToolInspector(history)
    assert inspector.current_index == 0
