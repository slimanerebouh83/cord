"""
CORD Models - Custom Model Provider Manager
Allows users and autonomous agents to create, list, delete, test, and switch custom model providers.
Persisted in ~/.cord/providers.json with full support for local, self-hosted, and cloud endpoints.
"""

from __future__ import annotations
import json
import os
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict

from cord.core.config import PROVIDER_PRESETS, ConfigManager, CordConfig


@dataclass
class CustomProvider:
    name: str
    base_url: str
    api_key: Optional[str] = None
    default_model: str = "default"
    models: List[str] = field(default_factory=list)
    api_format: str = "openai"  # openai, anthropic, gemini, ollama
    description: str = ""
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ProviderManager:
    """Manages custom and preset AI model providers persisted in ~/.cord/providers.json."""

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or (Path.home() / ".cord" / "providers.json")
        self._ensure_storage()

    def _ensure_storage(self) -> None:
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            if not self.storage_path.exists():
                self.storage_path.write_text("{}", encoding="utf-8")
        except Exception:
            pass

    def _load_custom(self) -> Dict[str, Dict[str, Any]]:
        try:
            if self.storage_path.exists():
                return json.loads(self.storage_path.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def _save_custom(self, data: Dict[str, Dict[str, Any]]) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def list_providers(self, include_presets: bool = True) -> List[Dict[str, Any]]:
        """Returns all registered providers (custom + built-in presets)."""
        results: List[Dict[str, Any]] = []
        custom_data = self._load_custom()

        for name, p in custom_data.items():
            entry = dict(p)
            entry["is_custom"] = True
            entry["id"] = name
            results.append(entry)

        if include_presets:
            for key, p in PROVIDER_PRESETS.items():
                if key not in custom_data:
                    results.append({
                        "id": key,
                        "name": p.get("name", key),
                        "base_url": p.get("base_url", ""),
                        "default_model": p.get("default_model", ""),
                        "models": p.get("models", []),
                        "api_format": p.get("api_format", "openai"),
                        "description": "Built-in preset",
                        "is_custom": False,
                    })

        return results

    def get_provider(self, name: str) -> Optional[Dict[str, Any]]:
        """Retrieves provider by name or preset ID."""
        key = name.strip().lower()
        custom = self._load_custom()
        if key in custom:
            entry = dict(custom[key])
            entry["is_custom"] = True
            entry["id"] = key
            return entry

        if key in PROVIDER_PRESETS:
            p = PROVIDER_PRESETS[key]
            return {
                "id": key,
                "name": p.get("name", key),
                "base_url": p.get("base_url", ""),
                "default_model": p.get("default_model", ""),
                "models": p.get("models", []),
                "api_format": p.get("api_format", "openai"),
                "description": "Built-in preset",
                "is_custom": False,
            }
        return None

    def add_provider(
        self,
        name: str,
        base_url: str,
        api_key: Optional[str] = None,
        default_model: str = "default",
        models: Optional[List[str]] = None,
        api_format: str = "openai",
        description: str = "",
    ) -> Dict[str, Any]:
        """Registers a new custom model provider."""
        key = name.strip().lower().replace(" ", "_")
        clean_url = base_url.strip().rstrip("/")
        model_list = models or [default_model]
        if default_model not in model_list:
            model_list.insert(0, default_model)

        provider = CustomProvider(
            name=name.strip(),
            base_url=clean_url,
            api_key=api_key.strip() if api_key else None,
            default_model=default_model.strip(),
            models=model_list,
            api_format=api_format.strip().lower(),
            description=description.strip(),
        )

        custom = self._load_custom()
        custom[key] = provider.to_dict()
        self._save_custom(custom)
        return provider.to_dict()

    def delete_provider(self, name: str) -> bool:
        """Deletes a custom model provider."""
        key = name.strip().lower().replace(" ", "_")
        custom = self._load_custom()
        if key in custom:
            del custom[key]
            self._save_custom(custom)
            return True
        return False

    def test_provider(self, name_or_url: str, timeout: float = 3.0) -> Dict[str, Any]:
        """Checks if a provider endpoint is responsive."""
        prov = self.get_provider(name_or_url)
        url = prov["base_url"] if prov else name_or_url.strip()

        # Try health endpoint or /models
        test_endpoints = [f"{url}/models", f"{url}/v1/models", url]
        last_error = ""

        for ep in test_endpoints:
            try:
                req = urllib.request.Request(ep, method="GET")
                if prov and prov.get("api_key"):
                    key = prov["api_key"]
                    # If env var name provided
                    if key in os.environ:
                        key = os.environ[key]
                    req.add_header("Authorization", f"Bearer {key}")

                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    if resp.status in (200, 204, 401, 403):
                        return {
                            "success": True,
                            "endpoint": ep,
                            "status_code": resp.status,
                            "message": f"Endpoint reachable (status {resp.status})",
                        }
            except urllib.error.HTTPError as e:
                # 401/403 means server exists and answered
                if e.code in (401, 403):
                    return {
                        "success": True,
                        "endpoint": ep,
                        "status_code": e.code,
                        "message": f"Server reachable (requires valid API key, HTTP {e.code})",
                    }
                last_error = f"HTTP {e.code}: {e.reason}"
            except Exception as e:
                last_error = str(e)

        return {
            "success": False,
            "endpoint": url,
            "error": last_error or "Connection refused / timed out",
        }

    def switch_to_provider(
        self,
        name: str,
        model: Optional[str] = None,
        config_mgr: Optional[ConfigManager] = None,
    ) -> Optional[CordConfig]:
        """Hot-switches active CORD session configuration to target provider."""
        prov = self.get_provider(name)
        if not prov:
            return None

        mgr = config_mgr or ConfigManager()
        cfg = mgr.config

        target_model = model or prov.get("default_model") or "default"
        cfg.provider = prov.get("api_format") or "openai"
        cfg.base_url = prov.get("base_url")
        cfg.model = target_model

        if prov.get("api_key"):
            key = prov["api_key"]
            if key in os.environ:
                key = os.environ[key]
            cfg.api_key = key

        mgr.save_global(cfg)
        return cfg


provider_mgr = ProviderManager()
