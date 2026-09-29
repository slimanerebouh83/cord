"""
Unit Tests for NITEE v3 - Planner Core Architecture
Tests StructuralTree, VisionMatcher, WaitOptimizer, ReflexEngine,
NiteeExecutor, SkillCompiler, and NiteePlannerTool.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from cord.nitee.structural_tree import StructuralTree, UIElementNode
from cord.nitee.vision_matcher import VisionMatcher, VisionObject
from cord.nitee.optimizer import WaitOptimizer
from cord.nitee.reflex_engine import ReflexEngine
from cord.nitee.executor import NiteeExecutor
from cord.nitee.skill_compiler import SkillCompiler
from cord.nitee.nitee_core import NiteeCore
from cord.tools.computer.nitee_tool import NiteePlannerTool


# ─────────────────────────────────────────────────────────────
# 1. Structural Tree Tests
# ─────────────────────────────────────────────────────────────

def test_ui_element_node_formatting():
    node1 = UIElementNode(
        id="n_12",
        control_type="Button",
        name="Save",
        automation_id="save-btn",
        center_x=500,
        center_y=300,
    )
    assert node1.to_tree_line() == 'n_12 Button "Save" #save-btn'

    node2 = UIElementNode(
        id="n_8",
        control_type="Edit",
        name="Email",
        value="user@x.com",
        center_x=200,
        center_y=150,
    )
    assert node2.to_tree_line() == 'n_8 Edit "Email" = "user@x.com"'

    node3 = UIElementNode(
        id="n_9",
        control_type="Edit",
        name="Password",
        is_password=True,
        value="secret",
    )
    # Value must NOT be printed for password nodes
    assert "[password]" in node3.to_tree_line()
    assert "secret" not in node3.to_tree_line()


def test_structural_tree_capture_fallback():
    tree = StructuralTree()
    tree_text, nodes = tree.capture()
    assert isinstance(tree_text, str)
    assert isinstance(nodes, dict)
    assert len(nodes) > 0
    # Every node ID must follow n_1, n_2... format
    for nid, node in nodes.items():
        assert nid.startswith("n_")
        assert tree.get_element(nid) is node


# ─────────────────────────────────────────────────────────────
# 2. Vision Matcher Tests
# ─────────────────────────────────────────────────────────────

def test_vision_object_formatting():
    v_obj = VisionObject(
        id="v_3",
        label="enemy",
        confidence=0.91,
        center_x=512,
        center_y=300,
    )
    assert v_obj.to_tree_line() == 'v_3 Item "enemy" #conf0.91 @512,300'


def test_vision_matcher_registry(tmp_path):
    matcher = VisionMatcher(templates_dir=tmp_path)
    assert not matcher.has_template("enemy")
    matcher.register_template("enemy", MagicMock())
    assert matcher.has_template("enemy")


# ─────────────────────────────────────────────────────────────
# 3. Wait Optimizer Tests
# ─────────────────────────────────────────────────────────────

def test_optimizer_learn_and_converge(tmp_path):
    opt_file = tmp_path / "test_optimizer.json"
    opt = WaitOptimizer(storage_path=opt_file)

    # First record
    entry = opt.record_wait("save", 200.0)
    assert entry["avg_ms"] == 200.0
    assert entry["samples"] == 1

    # Second record
    entry2 = opt.record_wait("save", 100.0)
    assert entry2["samples"] == 2
    assert entry2["avg_ms"] < 200.0

    # Persistence check
    opt2 = WaitOptimizer(storage_path=opt_file)
    learned = opt2.get_learned_wait("save")
    assert learned == entry2["avg_ms"]

    stats = opt2.get_stats()
    assert "save" in stats
    assert stats["save"]["samples"] == 2


# ─────────────────────────────────────────────────────────────
# 4. Reflex Engine Tests
# ─────────────────────────────────────────────────────────────

def test_reflex_engine_rules_evaluation():
    mock_matcher = MagicMock()
    # Mock vision objects: coin and enemy
    obj_enemy = VisionObject("v_1", "enemy", 0.90, center_x=960, center_y=540)
    mock_matcher.detect_objects.return_value = ("", {"v_1": obj_enemy})

    executed_actions = []

    def mock_executor(action_type, payload):
        executed_actions.append((action_type, payload["target"].label))

    engine = ReflexEngine(vision_matcher=mock_matcher, action_executor=mock_executor, frequency_hz=30)
    rules = [
        {"if": {"see": "enemy", "min_conf": 0.85}, "then": {"action": "CLICK_ON"}, "cooldown_ms": 100}
    ]

    result = engine.run_burst(rules=rules, reflex_seconds=0.2)
    assert result["total_firings"] >= 1
    assert any(a[0] == "CLICK_ON" and a[1] == "enemy" for a in executed_actions)


# ─────────────────────────────────────────────────────────────
# 5. Local Executor Tests
# ─────────────────────────────────────────────────────────────

def test_executor_batch_success(tmp_path):
    opt = WaitOptimizer(storage_path=tmp_path / "opt.json")
    executor = NiteeExecutor(optimizer=opt)

    elem_map = {
        "n_1": UIElementNode("n_1", "Button", name="Save", center_x=100, center_y=100),
        "n_2": UIElementNode("n_2", "Edit", name="Note", center_x=200, center_y=200),
    }

    plan = [
        {"step": 1, "action": "CLICK", "element_id": "n_1", "risk": "low"},
        {"step": 2, "action": "SET_TEXT", "element_id": "n_2", "value": "test note", "risk": "low"},
        {"step": 3, "action": "WAIT_STATE", "wait_label": "save_op", "risk": "low"},
        {"step": 4, "action": "DONE", "risk": "low"},
    ]

    with patch.object(executor, "_click_coords"), patch.object(executor, "_type_text"):
        res = executor.execute_batch(plan=plan, element_map=elem_map)
        assert res["success"] is True
        assert res["completed_steps"] >= 3
        assert len(res["errors"]) == 0


def test_executor_security_password_protection():
    executor = NiteeExecutor()
    elem_map = {
        "n_pwd": UIElementNode("n_pwd", "Edit", name="Pass", is_password=True, center_x=100, center_y=100),
    }
    plan = [
        {"step": 1, "action": "SET_TEXT", "element_id": "n_pwd", "value": "p@ss123", "risk": "low"}
    ]
    res = executor.execute_batch(plan=plan, element_map=elem_map)
    assert res["success"] is False
    assert any("password" in err.lower() for err in res["errors"])


def test_executor_vision_mode_refuses_set_text():
    executor = NiteeExecutor()
    elem_map = {
        "v_1": VisionObject("v_1", "textbox", 0.95, center_x=100, center_y=100)
    }
    plan = [
        {"step": 1, "action": "SET_TEXT", "element_id": "v_1", "value": "hello", "risk": "low"}
    ]
    res = executor.execute_batch(plan=plan, element_map=elem_map, is_vision_mode=True)
    assert res["success"] is False
    assert any("vision mode" in err.lower() for err in res["errors"])


def test_executor_high_risk_gating():
    executor = NiteeExecutor()
    elem_map = {
        "n_1": UIElementNode("n_1", "Button", name="Delete Account", center_x=100, center_y=100)
    }
    plan = [
        {"step": 1, "action": "CLICK", "element_id": "n_1", "risk": "high"}
    ]
    res = executor.execute_batch(plan=plan, element_map=elem_map, allow_high_risk=False)
    assert res["success"] is False
    assert res["needs_human_approval"] is True


# ─────────────────────────────────────────────────────────────
# 6. Skill Compiler Tests
# ─────────────────────────────────────────────────────────────

def test_skill_compiler(tmp_path):
    compiler = SkillCompiler(storage_dir=tmp_path)
    plan = [
        {"step": 1, "action": "CLICK", "element_id": "n_1"},
        {"step": 2, "action": "KEY", "value": "{Ctrl}s"},
        {"step": 3, "action": "DONE"},
    ]
    skill = compiler.compile(goal="Save user document", plan=plan, summary="Document saved cleanly")
    assert skill["name"] == "save_user_document"
    assert skill["step_count"] == 2  # DONE excluded from replay steps

    loaded = compiler.load_skill("save_user_document")
    assert loaded is not None
    assert loaded["goal"] == "Save user document"

    skills_list = compiler.list_skills()
    assert len(skills_list) == 1
    assert skills_list[0]["name"] == "save_user_document"


# ─────────────────────────────────────────────────────────────
# 7. NiteeCore End-to-End & Protocol Tests
# ─────────────────────────────────────────────────────────────

def test_nitee_core_parse_strict_json():
    core = NiteeCore()
    valid_json = """
    {
      "analysis": "Form is ready for input",
      "plan": [
        {"step": 1, "action": "CLICK", "element_id": "n_1", "risk": "low"},
        {"step": 2, "action": "DONE", "risk": "low"}
      ],
      "reflex_rules": [],
      "reflex_seconds": 0,
      "done": true,
      "summary": "Completed form click"
    }
    """
    parsed = core.parse_response(valid_json)
    assert parsed["analysis"] == "Form is ready for input"
    assert parsed["done"] is True
    assert len(parsed["plan"]) == 2

    # Malformed JSON should raise ValueError
    with pytest.raises(ValueError):
        core.parse_response("{invalid json")

    # Missing required field
    with pytest.raises(ValueError):
        core.parse_response('{"analysis": "test", "plan": []}')


# ─────────────────────────────────────────────────────────────
# 8. NiteePlannerTool Tests
# ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_nitee_tool_inspect():
    tool = NiteePlannerTool()
    res = await tool.execute(action="inspect", goal="Test inspection")
    assert res.success is True
    assert "<ui_tree>" in res.output
    assert "OPTIMIZER" in res.metadata


@pytest.mark.asyncio
async def test_nitee_tool_get_optimizer_stats():
    tool = NiteePlannerTool()
    res = await tool.execute(action="get_optimizer_stats")
    assert res.success is True
    assert "Learned wait stats" in res.output
