"""CORD Task System - Hierarchical Task Manager & Execution State Tracker"""
from __future__ import annotations
import json
import time
from pathlib import Path
from typing import List, Optional, Dict, Any
from rich.tree import Tree
from rich.panel import Panel
from rich.table import Table

from cord.tasks.task_state import TaskState
from cord.tasks.task_model import Task

STATE_STYLES = {
    TaskState.PENDING: ("dim cyan", "○"),
    TaskState.RUNNING: ("bold yellow", "▶"),
    TaskState.WAITING: ("yellow", "⏳"),
    TaskState.VERIFYING: ("bold blue", "🔍"),
    TaskState.COMPLETED: ("bold green", "✓"),
    TaskState.FAILED: ("bold red", "✗"),
    TaskState.CANCELLED: ("dim white", "⊘"),
    TaskState.BLOCKED: ("dim red", "⛔"),
}

class TaskManager:
    """Tracks and orchestrates hierarchical tasks, goals, subtasks, and verification."""

    def __init__(self, storage_dir: Optional[Path] = None):
        self.storage_dir = storage_dir or (Path.home() / ".cord" / "tasks")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.root_tasks: List[Task] = []
        self.current_goal: str = ""

    def set_goal(self, goal: str) -> None:
        self.current_goal = goal
        self.root_tasks.clear()

    def add_task(self, title: str, description: str = "", parent_id: Optional[str] = None) -> Task:
        if parent_id:
            parent = self.get_task(parent_id)
            if parent:
                return parent.add_subtask(title, description)

        task_id = f"task-{len(self.root_tasks) + 1}"
        task = Task(id=task_id, title=title, description=description)
        self.root_tasks.append(task)
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        for root in self.root_tasks:
            if root.id == task_id:
                return root
            res = root.find_subtask(task_id)
            if res:
                return res
        return None

    def update_task_state(self, task_id: str, new_state: TaskState, error: Optional[str] = None) -> bool:
        task = self.get_task(task_id)
        if not task:
            return False
        return task.transition_to(new_state, error=error)

    def get_next_pending_task(self) -> Optional[Task]:
        """Find the next actionable task (depth-first or root)."""
        def _find_pending(task: Task) -> Optional[Task]:
            if task.state == TaskState.PENDING:
                return task
            for st in task.subtasks:
                res = _find_pending(st)
                if res:
                    return res
            return None

        for root in self.root_tasks:
            res = _find_pending(root)
            if res:
                return res
        return None

    def get_active_task(self) -> Optional[Task]:
        """Return the currently executing or verifying task."""
        def _find_running(task: Task) -> Optional[Task]:
            if task.state in {TaskState.RUNNING, TaskState.VERIFYING}:
                return task
            for st in task.subtasks:
                res = _find_running(st)
                if res:
                    return res
            return None

        for root in self.root_tasks:
            res = _find_running(root)
            if res:
                return res
        return None

    def all_completed(self) -> bool:
        if not self.root_tasks:
            return False
        def _is_done(t: Task) -> bool:
            if t.state not in {TaskState.COMPLETED, TaskState.CANCELLED}:
                return False
            return all(_is_done(st) for st in t.subtasks)
        return all(_is_done(r) for r in self.root_tasks)

    def render_tree(self) -> Tree:
        title = f"[bold bright_white]Goal:[/bold bright_white] [cyan]{self.current_goal or 'Autonomous Plan'}[/cyan]"
        tree = Tree(title)

        def _add_nodes(parent_tree: Tree, task: Task):
            color, icon = STATE_STYLES.get(task.state, ("white", "•"))
            label = f"[{color}]{icon} [{task.id}] {task.title} ({task.state.value})[/{color}]"
            node = parent_tree.add(label)
            for st in task.subtasks:
                _add_nodes(node, st)

        for root in self.root_tasks:
            _add_nodes(tree, root)

        return tree

    def save_session(self, session_id: str) -> Path:
        data = {
            "goal": self.current_goal,
            "tasks": [t.to_dict() for t in self.root_tasks],
            "saved_at": time.time(),
        }
        file_path = self.storage_dir / f"{session_id}.json"
        file_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return file_path

    def load_session(self, session_id: str) -> bool:
        file_path = self.storage_dir / f"{session_id}.json"
        if not file_path.exists():
            return False
        data = json.loads(file_path.read_text(encoding="utf-8"))
        self.current_goal = data.get("goal", "")
        self.root_tasks = [Task.from_dict(t) for t in data.get("tasks", [])]
        return True

task_manager = TaskManager()
