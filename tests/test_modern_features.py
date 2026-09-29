"""
Tests for Modern CORD CLI Features:
- File Checkpoint & Undo Engine
- Web Documentation Fetcher
- Modern Provider Presets (Claude 3.7, Gemini 2.5, DeepSeek R1, etc.)
- Context Auto-Compaction
"""

import pytest
from pathlib import Path
from cord.core.config import PROVIDER_PRESETS, CordConfig
from cord.core.checkpoints import CheckpointManager
from cord.tools.web_tools import html_to_markdown, FetchWebPageTool
from cord.core.agent import CordAgent
from cord.tools.registry import ToolRegistry
from cord.core.permissions import PermissionGuard


def test_modern_provider_presets():
    # Verify new 2025/2026 providers exist
    assert "gemini" in PROVIDER_PRESETS
    assert "xai" in PROVIDER_PRESETS
    assert "together" in PROVIDER_PRESETS
    assert "openrouter" in PROVIDER_PRESETS

    # Verify modern models in presets
    openrouter_models = PROVIDER_PRESETS["openrouter"]["models"]
    assert "anthropic/claude-3.7-sonnet" in openrouter_models
    assert "deepseek/deepseek-r1" in openrouter_models
    assert "google/gemini-2.5-pro-exp-02-05" in openrouter_models
    assert "openai/o3-mini" in openrouter_models

    gemini_models = PROVIDER_PRESETS["gemini"]["models"]
    assert "gemini-2.5-pro-exp-02-05" in gemini_models
    assert "gemini-2.0-flash" in gemini_models


def test_checkpoint_undo_create_and_edit(tmp_path):
    mgr = CheckpointManager(workspace_path=tmp_path)
    test_file = tmp_path / "script.py"

    # Test 1: Snapshot before create -> undo should delete it
    mgr.snapshot(str(test_file), action="created")
    test_file.write_text("print('hello')", encoding="utf-8")
    assert test_file.exists()

    res = mgr.undo()
    assert "Reverted creation" in res
    assert not test_file.exists()

    # Test 2: Snapshot before edit -> undo should restore original content
    test_file.write_text("original_version = 1\n", encoding="utf-8")
    mgr.snapshot(str(test_file), action="edited")
    test_file.write_text("modified_version = 2\n", encoding="utf-8")

    res = mgr.undo()
    assert "Restored" in res
    assert test_file.read_text(encoding="utf-8") == "original_version = 1\n"


def test_html_to_markdown():
    html = """
    <html>
        <body>
            <h1>Library Documentation</h1>
            <p>Welcome to <code>cord-cli</code>. Visit <a href="https://example.com">the docs</a>.</p>
            <pre><code>def example():\n    return 42\n</code></pre>
            <script>alert('hidden');</script>
        </body>
    </html>
    """
    md = html_to_markdown(html)
    assert "# Library Documentation" in md
    assert "`cord-cli`" in md
    assert "[the docs](https://example.com)" in md
    assert "```" in md
    assert "def example():" in md
    assert "alert('hidden')" not in md  # Scripts stripped


def test_agent_context_compaction(tmp_path):
    cfg = CordConfig(workspace_dir=str(tmp_path))
    guard = PermissionGuard(cfg)
    registry = ToolRegistry(guard)
    agent = CordAgent(config=cfg, tool_registry=registry)

    # Populate 10 dummy messages
    for i in range(10):
        agent.messages.append({"role": "user" if i % 2 == 0 else "assistant", "content": f"Message {i}"})

    assert len(agent.messages) == 10
    res = agent.compact_context()
    assert "Context successfully compacted" in res
    assert len(agent.messages) <= 5
