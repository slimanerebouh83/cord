"""CORD Task System - Task & Subtask Data Models"""
from __future__ import annotations
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from cord.tasks.task_state import TaskState, VALID_TRANSITIONS

@dataclass
class Task:
    id: str
    title: str
    description: str = ""
    state: TaskState = TaskState.PENDING
    parent_id: Optional[str] = None
    subtasks: List[Task] = field(default_factory=list)
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    artifacts_created: List[str] = field(default_factory=list)
    artifacts_modified: List[str] = field(default_factory=list)
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    def transition_to(self, new_state: TaskState, error: Optional[str] = None) -> bool:
        """Attempt to transition this task to a new state based on valid transitions."""
        if new_state == self.state:
            return True

        valid_targets = VALID_TRANSITIONS.get(self.state, set())
        if new_state not in valid_targets:
            return False

        self.state = new_state
        if new_state == TaskState.RUNNING and not self.started_at:
            self.started_at = time.time()
        elif new_state in {TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED}:
            self.completed_at = time.time()

        if error:
            self.error = error
        return True

    def add_subtask(self, title: str, description: str = "") -> Task:
        sub_id = f"{self.id}.{len(self.subtasks) + 1}"
        subtask = Task(
            id=sub_id,
            title=title,
            description=description,
            parent_id=self.id
        )
        self.subtasks.append(subtask)
        return subtask

    def find_subtask(self, subtask_id: str) -> Optional[Task]:
        for st in self.subtasks:
            if st.id == subtask_id:
                return st
            res = st.find_subtask(subtask_id)
            if res:
                return res
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "state": self.state.value,
            "parent_id": self.parent_id,
            "subtasks": [st.to_dict() for st in self.subtasks],
            "tool_calls_count": len(self.tool_calls),
            "artifacts_created": self.artifacts_created,
            "artifacts_modified": self.artifacts_modified,
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Task:
        task = cls(
            id=data["id"],
            title=data["title"],
            description=data.get("description", ""),
            state=TaskState(data.get("state", "PENDING")),
            parent_id=data.get("parent_id"),
            error=data.get("error"),
            created_at=data.get("created_at", time.time()),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            artifacts_created=data.get("artifacts_created", []),
            artifacts_modified=data.get("artifacts_modified", []),
        )
        task.subtasks = [cls.from_dict(st) for st in data.get("subtasks", [])]
        return task
