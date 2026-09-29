"""
Tests for 100% Real Live Telemetry, Custom Model Providers, and In-Terminal Multi-Window Multiplexer.
"""

import pytest
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

from cord.ui.split_view import (
    calculate_real_cost,
    get_model_max_context,
    detect_installed_lsp_tools,
    render_sidebar_panel,
    sidebar_state,
)
from cord.models.provider_manager import ProviderManager, CustomProvider
from cord.tools.models.manage_providers import ManageProvidersTool
from cord.ui.multipane import MultiPaneManager, Pane
from cord.core.planner import PlanManager, plan_mgr
from cord.core.config import ConfigManager, CordConfig


# ==========================================
# 1. Real Live Telemetry & Cost Tests
# ==========================================

def test_real_cost_zero_tokens():
    assert calculate_real_cost("gemini-2.5-flash", 0, 0) == 0.0
    assert calculate_real_cost("claude-3-7-sonnet", 0, 0) == 0.0
    assert calculate_real_cost("gpt-4o", 0, 0) == 0.0


def test_real_cost_local_ollama_is_free():
    assert calculate_real_cost("ollama/qwen2.5-coder", 50000, 10000) == 0.0
    assert calculate_real_cost("local-model", 100000, 20000) == 0.0


def test_real_cost_gemini_and_claude():
    # Gemini 2.5 Flash: $0.075 / 1M in, $0.30 / 1M out
    # 1M in = $0.075, 1M out = $0.30 -> $0.375
    cost_gemini = calculate_real_cost("gemini-2.5-flash", 1_000_000, 1_000_000)
    assert abs(cost_gemini - 0.375) < 0.0001

    # Claude 3.7: $3.00 / 1M in, $15.00 / 1M out
    cost_claude = calculate_real_cost("claude-3-7-sonnet", 1_000_000, 1_000_000)
    assert abs(cost_claude - 18.0) < 0.001


def test_model_max_context():
    assert get_model_max_context("gemini-2.5-flash") == 1_048_576
    assert get_model_max_context("gemini-1.5-pro") == 2_000_000
    assert get_model_max_context("claude-3-7-sonnet") == 200_000
    assert get_model_max_context("gpt-4o") == 128_000
    assert get_model_max_context("deepseek-r1") == 64_000


def test_render_sidebar_panel_with_real_zero_data():
    panel = render_sidebar_panel(
        tokens=0,
        input_tokens=0,
        output_tokens=0,
        model="gemini-2.5-flash",
        mcp_mgr=None,
    )
    # Convert panel renderable to text string to inspect content
    content = str(panel.renderable)
    assert "0 tokens" in content
    assert "0% of" in content
    assert "$0.00 spend" in content
    assert "No MCP servers connected" in content


def test_render_sidebar_panel_with_real_plan():
    # Set a real active plan
    plan_mgr.create_plan("Build Authentication System", [
        "Implement JWT tokens",
        "Add bcrypt password hashing",
        "Write integration tests",
    ])
    plan_mgr.update_step(1, "completed")
    plan_mgr.update_step(2, "in_progress")

    panel = render_sidebar_panel(
        tokens=1250,
        input_tokens=1000,
        output_tokens=250,
        model="gemini-2.5-flash",
    )
    content = str(panel.renderable)
    assert "1,250 tokens" in content
    assert "[✓]" in content
    assert "[▶]" in content
    assert "Implement JWT tokens" in content

    # Clean up plan
    plan_mgr.current_plan = None


# ==========================================
# 2. Custom Provider Manager Tests
# ==========================================

def test_provider_manager_crud(tmp_path):
    storage = tmp_path / "providers.json"
    pm = ProviderManager(storage_path=storage)

    # 1. Initial list includes presets
    initial = pm.list_providers(include_presets=True)
    assert len(initial) > 0

    # 2. Add custom provider
    custom = pm.add_provider(
        name="my_vllm_cluster",
        base_url="http://192.168.1.100:8000/v1",
        api_key="secret-key-123",
        default_model="meta-llama/Llama-3.3-70B-Instruct",
        models=["meta-llama/Llama-3.3-70B-Instruct", "mistralai/Mistral-Small-24B"],
        api_format="openai",
        description="Local private vLLM compute server",
    )
    assert custom["name"] == "my_vllm_cluster"
    assert custom["default_model"] == "meta-llama/Llama-3.3-70B-Instruct"

    # 3. Retrieve provider
    retrieved = pm.get_provider("my_vllm_cluster")
    assert retrieved is not None
    assert retrieved["base_url"] == "http://192.168.1.100:8000/v1"
    assert retrieved["is_custom"] is True

    # 4. Delete provider
    deleted = pm.delete_provider("my_vllm_cluster")
    assert deleted is True
    assert pm.get_provider("my_vllm_cluster") is None


def test_provider_manager_switch_to_provider(tmp_path):
    storage = tmp_path / "providers.json"
    pm = ProviderManager(storage_path=storage)
    pm.add_provider(
        name="openrouter_test",
        base_url="https://openrouter.ai/api/v1",
        api_key="sk-or-v1-test",
        default_model="deepseek/deepseek-r1",
    )

    cfg_mgr = ConfigManager(workspace_path=tmp_path, home_cord_dir=tmp_path / "home")
    new_cfg = pm.switch_to_provider("openrouter_test", config_mgr=cfg_mgr)
    assert new_cfg is not None
    assert new_cfg.model == "deepseek/deepseek-r1"
    assert new_cfg.base_url == "https://openrouter.ai/api/v1"


# ==========================================
# 3. ManageProvidersTool Tests
# ==========================================

@pytest.mark.asyncio
async def test_manage_providers_tool(tmp_path):
    tool = ManageProvidersTool()

    # Test list
    res = await tool.execute(action="list")
    assert res.success is True
    assert "gemini" in res.output or "anthropic" in res.output

    # Test add
    add_res = await tool.execute(
        action="add",
        name="test_endpoint",
        base_url="http://localhost:1234/v1",
        default_model="local-model",
    )
    assert add_res.success is True
    assert "test_endpoint" in add_res.output

    # Test delete
    del_res = await tool.execute(action="delete", name="test_endpoint")
    assert del_res.success is True


# ==========================================
# 4. Multi-Window Multiplexer Tests
# ==========================================

def test_multipane_manager_vertical_split():
    mp = MultiPaneManager()
    assert len(mp.panes) == 1
    assert mp.active_id == 1
    assert mp.is_split is False

    # Split vertical
    p2 = mp.split_vertical(model="deepseek-r1", title="DeepSeek Terminal")
    assert len(mp.panes) == 2
    assert p2.id == 2
    assert mp.active_id == 2
    assert mp.split_type == "vertical"
    assert mp.is_split is True

    # Switch pane
    p_active = mp.switch_pane()
    assert p_active.id == 1
    assert mp.active_id == 1

    # Resize divider
    old_ratio = mp.split_ratio
    new_ratio = mp.resize_split(0.10)
    assert new_ratio == pytest.approx(old_ratio + 0.10, 0.001)

    # Mouse column resize
    mp.set_split_ratio_from_mouse(mouse_col=75, total_cols=100)
    assert mp.split_ratio == pytest.approx(0.75, 0.01)

    # Close pane
    closed = mp.close_pane(p2.id)
    assert closed is True
    assert len(mp.panes) == 1
    assert mp.is_split is False


def test_multipane_mouse_click_selection():
    mp = MultiPaneManager()
    mp.split_vertical(model="qwen2.5-coder")
    assert len(mp.panes) == 2

    # Divider is at 50% of 100 cols = col 50
    # Clicking col 20 (left of 50) switches to Pane 1
    clicked_id = mp.handle_mouse_click(col=20, row=10, total_cols=100, total_rows=30)
    assert clicked_id == 1
    assert mp.active_id == 1

    # Clicking col 80 (right of 50) switches to Pane 2
    clicked_id2 = mp.handle_mouse_click(col=80, row=10, total_cols=100, total_rows=30)
    assert clicked_id2 == 2
    assert mp.active_id == 2


def test_multipane_render_layout():
    mp = MultiPaneManager()
    mp.split_vertical(model="gpt-4o")
    layout = mp.render_multipane_layout(width=120, height=30)
    assert layout is not None
    # Layout should have left and right children
    assert "left" in [c.name for c in layout.children]
    assert "right" in [c.name for c in layout.children]


# ==========================================
# 5. Zero-Confirmation & Automatic Approval Tests
# ==========================================

def test_permission_guard_automatic_approval():
    from cord.core.permissions import PermissionGuard
    cfg = CordConfig()
    guard = PermissionGuard(cfg)

    # Shell command auto-approves without asking
    allowed, reason = guard.check_permission("run_shell", {"command": "git status"})
    assert allowed is True
    assert reason is None

    # Write file auto-approves without asking
    allowed, reason = guard.check_permission("write_file", {"path": "test.txt", "content": "hello"})
    assert allowed is True
    assert reason is None

    # Edit file auto-approves without asking
    allowed, reason = guard.check_permission("edit_file", {"path": "test.txt", "new_content": "world"})
    assert allowed is True
    assert reason is None


@pytest.mark.asyncio
async def test_ask_user_tool_auto_approves_instantly():
    from cord.tools.interactive_tools import AskUserTool
    tool = AskUserTool()
    res = await tool.execute(question="Do you agree with this file deletion?")
    assert res.success is True
    assert "[Auto-Approved]" in res.output


def test_permission_manager_auto_mode():
    from cord.permissions.manager import PermissionManager
    from cord.permissions.levels import PermissionLevel, RiskLevel
    pm = PermissionManager()
    allowed, reason = pm.check_and_request(
        tool_name="execute_command",
        required_level=PermissionLevel.ADMIN,
        risk=RiskLevel.HIGH,
        command="pytest",
    )
    assert allowed is True
    assert reason is None
