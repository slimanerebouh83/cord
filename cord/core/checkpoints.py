"""
CORD Core - File Checkpoint & Undo Engine
Automatically snapshots file states before modifications and enables /undo rollback.
"""

from __future__ import annotations
import shutil
import time
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, asdict

from cord.ui.console import ui


@dataclass
class Checkpoint:
    file_path: str
    backup_path: Optional[str]
    action: str  # "created" or "edited"
    timestamp: float
    description: str = ""


class CheckpointManager:
    """Manages file snapshots for instant undo and rollback."""

    def __init__(self, workspace_path: Optional[Path] = None):
        self.workspace_path = workspace_path or Path.cwd()
        self.backup_dir = self.workspace_path / ".cord" / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.history: List[Checkpoint] = []

    def snapshot(self, file_path: str, action: str = "edited", description: str = "") -> Checkpoint:
        """Captures the current state of a file before an edit or write."""
        target = Path(file_path).expanduser().resolve()
        ts = time.time()
        backup_file = None

        if target.exists() and target.is_file():
            filename = f"{target.stem}_{int(ts * 1000)}{target.suffix}.bak"
            backup_file = self.backup_dir / filename
            try:
                shutil.copy2(target, backup_file)
            except Exception as e:
                ui.print_warning(f"Could not snapshot {file_path}: {e}")
                backup_file = None
        else:
            action = "created"

        cp = Checkpoint(
            file_path=str(target),
            backup_path=str(backup_file) if backup_file else None,
            action=action,
            timestamp=ts,
            description=description,
        )
        self.history.append(cp)
        return cp

    def undo(self) -> Optional[str]:
        """Reverts the last file modification."""
        if not self.history:
            return None

        cp = self.history.pop()
        target = Path(cp.file_path)

        try:
            if cp.action == "created":
                # File was newly created, so undo means deleting it
                if target.exists():
                    target.unlink()
                    return f"Reverted creation of {target.name} (file removed)."
            elif cp.action == "edited" and cp.backup_path:
                bak = Path(cp.backup_path)
                if bak.exists():
                    shutil.copy2(bak, target)
                    return f"Restored {target.name} to previous state from backup."
        except Exception as e:
            return f"Failed to rollback {target.name}: {e}"

        return f"Rolled back action on {target.name}."


# Global checkpoint manager
checkpoint_mgr = CheckpointManager()
