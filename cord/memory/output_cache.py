"""CORD Memory - Output Cache for Large Command and Tool Outputs"""
from __future__ import annotations
import hashlib
import time
from pathlib import Path
from typing import Tuple

class OutputCache:
    """Caches large command outputs to disk to keep LLM context window fast and relevant."""

    def __init__(self, cache_dir: Path | None = None, max_chars: int = 2500):
        self.cache_dir = cache_dir or (Path.home() / ".cord" / "output_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_chars = max_chars

    def cache_and_truncate(self, content: str, prefix: str = "output") -> Tuple[str, bool, str | None]:
        """
        If content exceeds max_chars, save full content to disk and return:
        (truncated_summary, was_truncated, saved_file_path)
        """
        if len(content) <= self.max_chars:
            return content, False, None

        # Compute hash and save full content
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]
        timestamp = int(time.time())
        file_name = f"{prefix}_{timestamp}_{content_hash}.log"
        file_path = self.cache_dir / file_name
        file_path.write_text(content, encoding="utf-8", errors="replace")

        head_len = int(self.max_chars * 0.6)
        tail_len = int(self.max_chars * 0.3)

        head = content[:head_len]
        tail = content[-tail_len:]
        omitted = len(content) - (head_len + tail_len)

        summary = (
            f"{head}\n\n"
            f"[... {omitted} characters omitted by CORD output cache ...]\n"
            f"[Full output saved to: {file_path}]\n\n"
            f"{tail}"
        )
        return summary, True, str(file_path)

output_cache = OutputCache()
