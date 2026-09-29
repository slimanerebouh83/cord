"""
Tests for CORD CLI Configuration and Permissions.
"""

import pytest
from pathlib import Path
from cord.core.config import CordConfig, ConfigManager, PROVIDER_PRESETS, normalize_base_url
from cord.core.permissions import PermissionGuard, READ_ONLY_TOOLS


def test_config_defaults(tmp_path):
    home = tmp_path / "home"
    cfg_mgr = ConfigManager(workspace_path=tmp_path, home_cord_dir=home)
    cfg = cfg_mgr.config
    assert cfg.provider in PROVIDER_PRESETS
    assert cfg.permission_mode in ("yolo", "balanced")
    assert "rm" in str(cfg.dangerous_patterns)


def test_config_update(tmp_path):
    home = tmp_path / "home"
    cfg_mgr = ConfigManager(workspace_path=tmp_path, home_cord_dir=home)
    cfg_mgr.update(permission_mode="yolo", model="gpt-4o")
    assert cfg_mgr.config.permission_mode == "yolo"
    assert cfg_mgr.config.model == "gpt-4o"


def test_permission_guard_dangerous_detection():
    cfg = CordConfig(permission_mode="yolo")
    guard = PermissionGuard(cfg)
    
    assert guard.is_dangerous_command("rm -rf /")
    assert guard.is_dangerous_command("del /s C:\\")
    assert guard.is_dangerous_command("format D:")
    assert not guard.is_dangerous_command("pytest -v")
    assert not guard.is_dangerous_command("ls -la")


def test_permission_guard_balanced_mode():
    cfg = CordConfig(permission_mode="balanced")
    guard = PermissionGuard(cfg)

    # Read-only tools should be auto-approved
    allowed, _ = guard.check_permission("read_file", {"path": "test.txt"})
    assert allowed is True

    allowed, _ = guard.check_permission("list_dir", {})
    assert allowed is True

    allowed, _ = guard.check_permission("grep_search", {"query": "foo"})
    assert allowed is True


def test_normalize_base_url():
    url, note = normalize_base_url("https://openrouter.ai/api/v1/chat/completions")
    assert url == "https://openrouter.ai/api/v1"
    assert note is not None
    assert "/chat/completions" in note

    url, note = normalize_base_url("https://openrouter.ai/api/v1/chat")
    assert url == "https://openrouter.ai/api/v1"
    assert note is not None

    url, note = normalize_base_url("https://api.anthropic.com/v1/messages")
    assert url == "https://api.anthropic.com/v1"
    assert note is not None

    # Normal base URL should have no notice
    url, note = normalize_base_url("https://openrouter.ai/api/v1")
    assert url == "https://openrouter.ai/api/v1"
    assert note is None

    # CordConfig auto-cleans base_url on initialization
    cfg = CordConfig(base_url="https://openrouter.ai/api/v1/chat/completions/")
    assert cfg.base_url == "https://openrouter.ai/api/v1"

