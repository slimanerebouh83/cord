"""
Tests for CORD CLI Native Tools.
"""

import pytest
import asyncio
from pathlib import Path
from cord.tools.file_tools import ReadFileTool, WriteFileTool, EditFileTool, ListDirTool, FindFilesTool
from cord.tools.search_tools import GrepSearchTool
from cord.tools.shell_tools import RunShellTool


@pytest.mark.asyncio
async def test_file_write_read_edit(tmp_path):
    test_file = tmp_path / "hello.py"
    
    # 1. Write file
    writer = WriteFileTool()
    write_res = await writer.execute(path=str(test_file), content="print('hello world')\nx = 1\n")
    assert write_res.success is True
    assert test_file.exists()

    # 2. Read file
    reader = ReadFileTool()
    read_res = await reader.execute(path=str(test_file))
    assert read_res.success is True
    assert "hello world" in read_res.output
    assert "   1 | print('hello world')" in read_res.output

    # 3. Edit file
    editor = EditFileTool()
    edit_res = await editor.execute(
        path=str(test_file),
        old_content="x = 1",
        new_content="x = 42\ny = 100",
    )
    assert edit_res.success is True
    assert "Diff:" in edit_res.output
    
    # Verify updated content
    content = test_file.read_text(encoding="utf-8")
    assert "x = 42" in content
    assert "y = 100" in content


@pytest.mark.asyncio
async def test_find_and_grep(tmp_path):
    f1 = tmp_path / "app.py"
    f2 = tmp_path / "config.py"
    f1.write_text("def run():\n    print('secret_key_123')\n", encoding="utf-8")
    f2.write_text("TOKEN = 'secret_key_123'\n", encoding="utf-8")

    # Find files
    finder = FindFilesTool()
    find_res = await finder.execute(pattern="*.py", path=str(tmp_path))
    assert find_res.success is True
    assert "app.py" in find_res.output
    assert "config.py" in find_res.output

    # Grep search
    grepper = GrepSearchTool()
    grep_res = await grepper.execute(query="secret_key_123", path=str(tmp_path))
    assert grep_res.success is True
    assert "Found 2 match(es)" in grep_res.output


@pytest.mark.asyncio
async def test_run_shell():
    shell = RunShellTool()
    res = await shell.execute(command="python -c \"print('CORD_CLI_TEST_OK')\"")
    assert res.success is True
    assert "CORD_CLI_TEST_OK" in res.output
