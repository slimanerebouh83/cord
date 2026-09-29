"""CORD Memory - Conversation Session History & Resumption Manager"""
from __future__ import annotations
import os
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

class SessionManager:
    """Manages persistent conversation sessions on disk, enabling session switching, restoration, and file-scoped tracking."""

    def __init__(self, sessions_dir: Optional[Path] = None):
        self.sessions_dir = sessions_dir or (Path.home() / ".cord" / "sessions")
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.current_session_id: str = f"session_{time.strftime('%Y%m%d_%H%M%S')}"
        self.current_target_file: Optional[str] = None
        self.current_changes: List[Dict[str, Any]] = []
        self.current_ui_events: List[Dict[str, Any]] = []

    def get_new_session_id(self, target_file: Optional[str] = None) -> str:
        self.current_session_id = f"session_{time.strftime('%Y%m%d_%H%M%S')}"
        self.current_target_file = target_file
        self.current_changes.clear()
        self.current_ui_events.clear()
        return self.current_session_id

    def clear_current_session(self) -> None:
        """Completely purges memory and history state for the active session."""
        self.current_changes.clear()
        self.current_ui_events.clear()
        self.current_target_file = None

    def record_ui_event(self, event_type: str, **kwargs: Any) -> Dict[str, Any]:
        """Records a rich terminal event (user query, model thought, answer, tool badge, diff) for high-fidelity replay."""
        evt = {
            "type": event_type,
            "timestamp": time.time(),
            **kwargs
        }
        self.current_ui_events.append(evt)
        return evt

    def set_target_file(self, target_file: Optional[str]) -> None:
        """Sets the file reference for the current active conversation."""
        self.current_target_file = target_file

    def record_session_change(
        self,
        file_path: str,
        action: str,
        diff: str = "",
        lines_added: int = 0,
        lines_removed: int = 0,
        description: str = "",
    ) -> Dict[str, Any]:
        """Records a file modification into the current session's changelog."""
        change = {
            "timestamp": time.time(),
            "file": file_path,
            "filename": Path(file_path).name,
            "action": action,  # "edited", "created", "deleted"
            "diff": diff,
            "lines_added": lines_added,
            "lines_removed": lines_removed,
            "description": description,
        }
        self.current_changes.append(change)
        return change

    def get_session_changes(self, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns the list of changes made during the specified session (or current)."""
        if session_id is None or session_id == self.current_session_id:
            return list(self.current_changes)
        
        data = self.load_session(session_id)
        if data:
            return data.get("changes", [])
        return []

    def save_session(
        self,
        messages: List[Dict[str, Any]],
        model: str = "",
        mode: str = "agent",
        session_id: Optional[str] = None,
        target_file: Optional[str] = None,
    ) -> Path:
        sid = session_id or self.current_session_id
        file_path = self.sessions_dir / f"{sid}.json"
        tfile = target_file if target_file is not None else self.current_target_file

        # Generate title from first user message if available
        title = f"Session ({Path(tfile).name})" if tfile else "New Session"
        for m in messages:
            if m.get("role") == "user":
                content = m.get("content", "")
                if isinstance(content, str) and content.strip():
                    first_line = content.strip().splitlines()[0]
                    title = first_line.replace("\n", " ")[:60]
                    if tfile and Path(tfile).name not in title:
                        title = f"[{Path(tfile).name}] {title}"
                    break

        data = {
            "session_id": sid,
            "title": title,
            "target_file": tfile,
            "created_at": time.time(),
            "updated_at": time.time(),
            "model": model,
            "mode": mode,
            "message_count": len(messages),
            "messages": messages,
            "changes": self.current_changes,
            "ui_events": self.current_ui_events,
        }

        file_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return file_path

    def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        clean_id = session_id.replace(".json", "")
        file_path = self.sessions_dir / f"{clean_id}.json"
        if not file_path.exists():
            for f in self.sessions_dir.glob("*.json"):
                if clean_id in f.name:
                    file_path = f
                    break

        if not file_path.exists():
            return None

        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            self.current_session_id = data.get("session_id", clean_id)
            self.current_target_file = data.get("target_file")
            self.current_changes = data.get("changes", [])
            self.current_ui_events = data.get("ui_events", [])
            return data
        except Exception:
            return None

    def list_sessions(self, target_file: Optional[str] = None) -> List[Dict[str, Any]]:
        sessions = []
        for f in sorted(self.sessions_dir.glob("*.json"), key=os.path.getmtime, reverse=True):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                s_tfile = data.get("target_file")
                
                # Filter by target file if specified
                if target_file is not None:
                    if target_file == "__none__" and s_tfile:
                        continue
                    elif target_file != "__none__" and s_tfile != target_file:
                        continue

                changes = data.get("changes", [])
                tot_added = sum(c.get("lines_added", 0) for c in changes)
                tot_removed = sum(c.get("lines_removed", 0) for c in changes)

                sessions.append({
                    "id": data.get("session_id", f.stem),
                    "title": data.get("title", "Untitled Session"),
                    "target_file": s_tfile,
                    "updated_at": data.get("updated_at", f.stat().st_mtime),
                    "message_count": data.get("message_count", len(data.get("messages", []))),
                    "model": data.get("model", "unknown"),
                    "mode": data.get("mode", "agent"),
                    "file_path": str(f),
                    "changes_count": len(changes),
                    "lines_added": tot_added,
                    "lines_removed": tot_removed,
                })
            except Exception:
                continue
        return sessions

    def delete_session(self, session_id: str) -> bool:
        clean_id = session_id.replace(".json", "")
        file_path = self.sessions_dir / f"{clean_id}.json"
        if file_path.exists():
            file_path.unlink()
            return True
        return False

session_manager = SessionManager()
