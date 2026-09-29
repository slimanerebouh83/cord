"""
CORD Tools - Ollama Model Management Tool
Allows the agent and user to list local models, pull new models, check daemon status, and switch models.
"""

from __future__ import annotations
from typing import Optional
from cord.tools.base import BaseTool, ToolResult
from cord.models.ollama_manager import ollama_mgr
from cord.core.config import ConfigManager


class OllamaModelTool(BaseTool):
    name = "ollama_model"
    description = (
        "Interact with the local Ollama AI model server. Supports 'status' (check if Ollama is running), "
        "'list' (discover all locally installed models), 'pull' (download a new model like 'deepseek-r1:8b' or 'qwen2.5-coder:7b'), "
        "and 'switch' (make a local Ollama model the active brain for CORD)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["status", "list", "pull", "switch"],
                "description": "Action to perform on Ollama",
            },
            "model_name": {
                "type": "string",
                "description": "Model tag or identifier (e.g. 'deepseek-r1:8b', 'qwen2.5-coder:7b', 'llama3.3')",
            },
        },
        "required": ["action"],
    }

    def __init__(self, config_mgr: Optional[ConfigManager] = None):
        super().__init__()
        self.config_mgr = config_mgr or ConfigManager()

    async def execute(self, action: str, model_name: Optional[str] = None, **kwargs) -> ToolResult:
        if action == "status":
            running = ollama_mgr.is_running()
            if running:
                return ToolResult(
                    success=True,
                    output=f"✔ Ollama server is ONLINE and responding at {ollama_mgr.base_url}.",
                )
            else:
                return ToolResult(
                    success=False,
                    output=f"❌ Ollama server is OFFLINE or unreachable at {ollama_mgr.base_url}. Ensure 'ollama serve' is running.",
                )

        elif action == "list":
            running = ollama_mgr.is_running()
            if not running:
                return ToolResult(
                    success=False,
                    output=f"❌ Ollama is not running. Launch Ollama first to access local models.",
                )
            models = ollama_mgr.list_models()
            if not models:
                return ToolResult(
                    success=True,
                    output="Ollama is running, but no models are currently installed. Use ollama_model(action='pull', model_name='deepseek-r1:8b') to download a model.",
                )
            lines = [f"Found {len(models)} local Ollama model(s):"]
            for m in models:
                lines.append(f"- 🦙 [bold cyan]{m['name']}[/bold cyan] │ Size: {m['size']} │ Digest: {m['digest']}")
            return ToolResult(success=True, output="\n".join(lines))

        elif action == "pull":
            if not model_name:
                return ToolResult(success=False, output="Parameter 'model_name' is required to pull a model.")
            res = await ollama_mgr.pull_model(model_name)
            if res["success"]:
                return ToolResult(
                    success=True,
                    output=f"✔ Successfully pulled model '{model_name}'. Ready for inference!\nOutput: {res.get('output', '')[:300]}",
                )
            return ToolResult(
                success=False,
                output=f"❌ Failed to pull '{model_name}': {res.get('error')}",
            )

        elif action == "switch":
            if not model_name:
                return ToolResult(success=False, output="Parameter 'model_name' is required to switch active model.")
            cfg = ollama_mgr.switch_to_ollama(model_name, self.config_mgr)
            return ToolResult(
                success=True,
                output=f"✔ Switched active CORD model to local Ollama: [bold white]{cfg.model}[/bold white] at {cfg.base_url}.",
            )

        return ToolResult(success=False, output=f"Unknown action: '{action}'")
