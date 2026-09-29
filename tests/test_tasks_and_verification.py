"""Tests for TaskManager, TaskState transitions, VerificationEngine, and OutputCache"""
import pytest
import tempfile
from pathlib import Path

from cord.tasks.task_state import TaskState, VALID_TRANSITIONS
from cord.tasks.task_model import Task
from cord.tasks.task_manager import TaskManager
from cord.core.verification_engine import VerificationEngine
from cord.memory.output_cache import OutputCache


def test_task_state_transitions():
    task = Task(id="task-1", title="Build Feature")
    assert task.state == TaskState.PENDING

    # Valid transition to RUNNING
    assert task.transition_to(TaskState.RUNNING) is True
    assert task.state == TaskState.RUNNING
    assert task.started_at is not None

    # Valid transition to VERIFYING
    assert task.transition_to(TaskState.VERIFYING) is True
    assert task.state == TaskState.VERIFYING

    # Valid transition to COMPLETED
    assert task.transition_to(TaskState.COMPLETED) is True
    assert task.state == TaskState.COMPLETED
    assert task.completed_at is not None

    # Invalid transition from COMPLETED to RUNNING
    assert task.transition_to(TaskState.RUNNING) is False
    assert task.state == TaskState.COMPLETED


def test_hierarchical_task_tree():
    with tempfile.TemporaryDirectory() as tmp_dir:
        mgr = TaskManager(storage_dir=Path(tmp_dir))
        mgr.set_goal("Refactor Database Layer")

        t1 = mgr.add_task("Create Migration")
        assert t1.id == "task-1"

        # Subtasks
        sub1 = mgr.add_task("Write schema SQL", parent_id=t1.id)
        assert sub1.id == "task-1.1"
        assert sub1.parent_id == "task-1"

        sub2 = mgr.add_task("Run Alembic Upgrade", parent_id=t1.id)
        assert sub2.id == "task-1.2"

        # Lookup
        found = mgr.get_task("task-1.2")
        assert found is not None
        assert found.title == "Run Alembic Upgrade"

        # State updates
        assert mgr.update_task_state("task-1.1", TaskState.RUNNING) is True
        assert mgr.get_active_task().id == "task-1.1"

        mgr.update_task_state("task-1.1", TaskState.COMPLETED)
        mgr.update_task_state("task-1.2", TaskState.COMPLETED)
        mgr.update_task_state("task-1", TaskState.COMPLETED)

        assert mgr.all_completed() is True

        # Persistence save and load
        saved_file = mgr.save_session("session_test")
        assert saved_file.exists()

        mgr2 = TaskManager(storage_dir=Path(tmp_dir))
        loaded = mgr2.load_session("session_test")
        assert loaded is True
        assert mgr2.current_goal == "Refactor Database Layer"
        assert len(mgr2.root_tasks) == 1
        assert len(mgr2.root_tasks[0].subtasks) == 2


def test_verification_engine_syntax_and_json():
    engine = VerificationEngine()
    with tempfile.TemporaryDirectory() as tmp_dir:
        dir_path = Path(tmp_dir)

        # Valid Python file
        valid_py = dir_path / "valid.py"
        valid_py.write_text("def add(a: int, b: int) -> int:\n    return a + b\n", encoding="utf-8")
        ok, err = engine.check_file_syntax(valid_py)
        assert ok is True
        assert err is None

        # Invalid Python syntax file
        invalid_py = dir_path / "invalid.py"
        invalid_py.write_text("def broken(:\n    return\n", encoding="utf-8")
        ok, err = engine.check_file_syntax(invalid_py)
        assert ok is False
        assert "SyntaxError" in err

        # Valid JSON
        valid_json = dir_path / "config.json"
        valid_json.write_text('{"name": "cord", "active": true}', encoding="utf-8")
        ok, err = engine.check_file_syntax(valid_json)
        assert ok is True
        assert err is None

        # Invalid JSON
        invalid_json = dir_path / "bad.json"
        invalid_json.write_text('{unquoted_key: 123,}', encoding="utf-8")
        ok, err = engine.check_file_syntax(invalid_json)
        assert ok is False
        assert "JSON" in err


def test_output_cache():
    with tempfile.TemporaryDirectory() as tmp_dir:
        cache = OutputCache(cache_dir=Path(tmp_dir), max_chars=100)

        # Short content
        short = "Everything is fine."
        out, truncated, file_path = cache.cache_and_truncate(short)
        assert truncated is False
        assert file_path is None
        assert out == short

        # Long content
        long_content = "Line of output data!\n" * 20
        out, truncated, file_path = cache.cache_and_truncate(long_content)
        assert truncated is True
        assert file_path is not None
        assert Path(file_path).exists()
        assert "omitted by CORD output cache" in out
