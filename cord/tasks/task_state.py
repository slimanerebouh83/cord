"""CORD Task System - Task Lifecycle States and Transitions"""
from __future__ import annotations
from enum import Enum

class TaskState(str, Enum):
    PENDING = "PENDING"          # Created, awaiting execution
    RUNNING = "RUNNING"          # Currently executing tools/actions
    WAITING = "WAITING"          # Waiting for user input, external process, or subagent
    VERIFYING = "VERIFYING"      # Running automated verification/tests
    COMPLETED = "COMPLETED"      # Successfully verified and closed
    FAILED = "FAILED"            # Execution failed or verification rejected
    CANCELLED = "CANCELLED"      # Explicitly cancelled by user or supervisor
    BLOCKED = "BLOCKED"          # Blocked by unresolved dependencies

# Valid state transitions
VALID_TRANSITIONS = {
    TaskState.PENDING: {TaskState.RUNNING, TaskState.COMPLETED, TaskState.CANCELLED, TaskState.BLOCKED},
    TaskState.BLOCKED: {TaskState.PENDING, TaskState.CANCELLED},
    TaskState.RUNNING: {TaskState.WAITING, TaskState.VERIFYING, TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED},
    TaskState.WAITING: {TaskState.RUNNING, TaskState.CANCELLED, TaskState.FAILED},
    TaskState.VERIFYING: {TaskState.COMPLETED, TaskState.FAILED, TaskState.RUNNING},
    TaskState.FAILED: {TaskState.PENDING, TaskState.RUNNING, TaskState.CANCELLED},  # Retry allowed
    TaskState.CANCELLED: {TaskState.PENDING},  # Can be re-opened
    TaskState.COMPLETED: set(),  # Terminal state (unless explicitly cloned/re-opened)
}
