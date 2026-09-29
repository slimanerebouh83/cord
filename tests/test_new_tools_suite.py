"""Tests for the new modular tools across Developer, Project, Git, and Filesystem suites"""
import pytest
import tempfile
from pathlib import Path

from cord.tools import get_default_tools
from cord.tools.project.detect_language import DetectLanguageTool
from cord.tools.project.detect_package_manager import DetectPackageManagerTool
from cord.tools.project.detect_framework import DetectFrameworkTool
from cord.tools.project.inspect_project import InspectProjectTool
from cord.tools.developer.run_formatter import RunFormatterTool
from cord.tools.developer.run_linter import RunLinterTool
from cord.tools.git.git_status import GitStatusTool


def test_get_default_tools_registry():
    tools = get_default_tools()
    assert len(tools) >= 40
    names = {t.name for t in tools}

    # Core categories verified
    assert "read_file" in names
    assert "write_file" in names
    assert "execute_command" in names
    assert "git_status" in names
    assert "run_tests" in names
    assert "run_formatter" in names
    assert "run_linter" in names
    assert "inspect_project" in names
    assert "detect_language" in names
    assert "computer_mouse" in names
    assert "computer_keyboard" in names
    assert "computer_screenshot" in names


@pytest.mark.asyncio
async def test_project_language_and_package_detection():
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        (root / "main.py").write_text("print('hello')", encoding="utf-8")
        (root / "helper.py").write_text("pass", encoding="utf-8")
        (root / "pyproject.toml").write_text("[project]\nname='demo'\ndependencies=['fastapi']\n", encoding="utf-8")

        # Detect Language
        lang_tool = DetectLanguageTool()
        res = await lang_tool.execute(path=str(root))
        assert res.success is True
        assert "Python" in res.output

        # Detect Package Manager
        pm_tool = DetectPackageManagerTool()
        res_pm = await pm_tool.execute(path=str(root))
        assert res_pm.success is True
        assert "pip" in res_pm.output

        # Detect Framework
        fw_tool = DetectFrameworkTool()
        res_fw = await fw_tool.execute(path=str(root))
        assert res_fw.success is True
        assert "FastAPI" in res_fw.output

        # Inspect Project
        inspect_tool = InspectProjectTool()
        res_ins = await inspect_tool.execute(root_path=str(root))
        assert res_ins.success is True
        assert "pyproject.toml" in res_ins.output
