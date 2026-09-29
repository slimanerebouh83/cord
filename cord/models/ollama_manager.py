"""
CORD Models - Local Ollama Model Manager
Handles daemon health detection, live model discovery (/api/tags), pulling, and hot-switching.
"""

from __future__ import annotations
import asyncio
import json
import os
import shutil
import socket
import urllib.request
from typing import Dict, List, Optional, Any
from cord.core.config import ConfigManager, CordConfig


class OllamaManager:
    """Discovers and orchestrates local Ollama models."""

    DEFAULT_BASE_URL = "http://127.0.0.1:11434"

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or os.environ.get("OLLAMA_API_BASE") or self.DEFAULT_BASE_URL).rstrip("/")
        self.ollama_bin = shutil.which("ollama") or "ollama"

    def is_running(self, timeout_sec: float = 1.5) -> bool:
        """Verifies whether the local Ollama daemon is reachable."""
        try:
            url = f"{self.base_url}/api/tags"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                return resp.status == 200
        except Exception:
            return False

    def list_models(self) -> List[Dict[str, Any]]:
        """Queries Ollama for all installed/downloaded local models."""
        # 1. Try HTTP API first
        try:
            url = f"{self.base_url}/api/tags"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models = data.get("models", [])
                results = []
                for m in models:
                    size_b = m.get("size", 0)
                    size_gb = f"{size_b / (1024**3):.1f} GB" if size_b > 1024**3 else f"{size_b / (1024**2):.0f} MB"
                    results.append({
                        "name": m.get("name"),
                        "model": m.get("model"),
                        "size": size_gb,
                        "digest": m.get("digest", "")[:12],
                        "modified_at": m.get("modified_at", ""),
                    })
                return results
        except Exception:
            pass

        # 2. Fallback to CLI
        try:
            import subprocess
            res = subprocess.run(
                [self.ollama_bin, "list"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=3.0,
            )
            if res.returncode == 0:
                lines = res.stdout.strip().splitlines()
                results = []
                if len(lines) > 1:
                    for line in lines[1:]:
                        parts = line.split()
                        if parts:
                            results.append({
                                "name": parts[0],
                                "model": parts[0],
                                "size": parts[2] if len(parts) > 2 else "Unknown",
                                "digest": parts[1] if len(parts) > 1 else "",
                                "modified_at": " ".join(parts[3:]) if len(parts) > 3 else "",
                            })
                return results
        except Exception:
            pass

        return []

    async def pull_model(self, model_name: str, timeout: float = 300.0) -> Dict[str, Any]:
        """Downloads/pulls a model using the Ollama CLI."""
        clean_name = model_name.strip()
        try:
            proc = await asyncio.create_subprocess_exec(
                self.ollama_bin, "pull", clean_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            out = stdout_b.decode("utf-8", errors="replace")
            err = stderr_b.decode("utf-8", errors="replace")
            success = (proc.returncode == 0)
            return {
                "success": success,
                "model": clean_name,
                "output": out or err,
                "error": err if not success else None,
            }
        except asyncio.TimeoutError:
            return {
                "success": False,
                "model": clean_name,
                "error": f"Pull operation timed out after {timeout}s",
            }
        except Exception as e:
            return {
                "success": False,
                "model": clean_name,
                "error": str(e),
            }

    def switch_to_ollama(self, model_name: str, config_mgr: ConfigManager) -> CordConfig:
        """Sets active model to local Ollama with zero API-key constraints."""
        cfg = config_mgr.config
        cfg.provider = "ollama"
        cfg.base_url = f"{self.base_url}/v1"
        cfg.model = model_name.strip()
        cfg.api_format = "openai"
        if not cfg.api_key:
            cfg.api_key = "ollama"  # Dummy key required by OpenAI client
        config_mgr.save_global(cfg)
        return cfg


ollama_mgr = OllamaManager()
