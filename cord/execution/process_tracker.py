"""
CORD Execution - Process Tracker
Tracks background subprocesses started by the agent, capturing real-time logs,
status, uptime, and providing non-blocking output inspection.
"""

from __future__ import annotations
import subprocess
import threading
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field


@dataclass
class TrackedProcess:
    id: str
    command: str
    pid: int
    process: Any
    start_time: float = field(default_factory=time.time)
    stdout_lines: List[str] = field(default_factory=list)
    stderr_lines: List[str] = field(default_factory=list)
    exit_code: Optional[int] = None
    _threads: List[threading.Thread] = field(default_factory=list)

    def is_alive(self) -> bool:
        if self.process is None:
            return False
        if not hasattr(self.process, "poll"):
            return True
        try:
            ret = self.process.poll()
            if ret is not None:
                self.exit_code = ret
                return False
        except Exception:
            return False
        return True


class ProcessTracker:
    """Manages active background child processes with non-blocking log capturing."""

    _instance: Optional[ProcessTracker] = None

    def __init__(self):
        self.processes: Dict[str, TrackedProcess] = {}

    @classmethod
    def get(cls) -> ProcessTracker:
        if cls._instance is None:
            cls._instance = ProcessTracker()
        return cls._instance

    def register(self, proc_id: str, command: str, pid: int, process_obj: Any) -> TrackedProcess:
        tp = TrackedProcess(id=proc_id, command=command, pid=pid, process=process_obj)
        self.processes[proc_id] = tp

        # Start non-blocking thread readers if pipes are available
        if hasattr(process_obj, "stdout") and process_obj.stdout:
            t_out = threading.Thread(
                target=self._stream_reader,
                args=(process_obj.stdout, tp.stdout_lines),
                daemon=True,
            )
            t_out.start()
            tp._threads.append(t_out)

        if hasattr(process_obj, "stderr") and process_obj.stderr:
            t_err = threading.Thread(
                target=self._stream_reader,
                args=(process_obj.stderr, tp.stderr_lines),
                daemon=True,
            )
            t_err.start()
            tp._threads.append(t_err)

        return tp

    @staticmethod
    def _stream_reader(pipe, dest_list: List[str], max_lines: int = 2000):
        try:
            for raw_line in iter(pipe.readline, b""):
                if not raw_line:
                    break
                line = raw_line.decode(errors="replace").rstrip()
                dest_list.append(line)
                if len(dest_list) > max_lines:
                    del dest_list[:500]
        except Exception:
            pass
        finally:
            try:
                pipe.close()
            except Exception:
                pass

    def stop(self, proc_id: str) -> bool:
        tp = self.processes.get(proc_id)
        if not tp:
            return False
        try:
            tp.process.terminate()
            tp.is_alive()
            return True
        except Exception:
            return False

    def get_logs(self, proc_id: str, tail: int = 50) -> Dict[str, Any]:
        tp = self.processes.get(proc_id)
        if not tp:
            return {"success": False, "error": f"Process '{proc_id}' not found."}

        alive = tp.is_alive()
        stdout_tail = tp.stdout_lines[-tail:] if tp.stdout_lines else []
        stderr_tail = tp.stderr_lines[-tail:] if tp.stderr_lines else []

        combined = []
        if stdout_tail:
            combined.append("[STDOUT]\n" + "\n".join(stdout_tail))
        if stderr_tail:
            combined.append("[STDERR]\n" + "\n".join(stderr_tail))

        return {
            "success": True,
            "proc_id": proc_id,
            "pid": tp.pid,
            "command": tp.command,
            "status": "running" if alive else f"terminated (exit {tp.exit_code})",
            "uptime_seconds": int(time.time() - tp.start_time),
            "output": "\n".join(combined) if combined else "(No output recorded yet)",
        }

    def list_all(self) -> Dict[str, Dict[str, Any]]:
        results = {}
        for pid_key, tp in list(self.processes.items()):
            alive = tp.is_alive()
            status = "running" if alive else f"terminated ({tp.exit_code})"
            results[pid_key] = {
                "command": tp.command,
                "pid": tp.pid,
                "status": status,
                "uptime_seconds": int(time.time() - tp.start_time),
                "total_stdout_lines": len(tp.stdout_lines),
                "total_stderr_lines": len(tp.stderr_lines),
            }
        return results


process_tracker = ProcessTracker.get()
