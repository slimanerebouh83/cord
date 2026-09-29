"""
CORD Tools - Voice & Audio Models Management Tool
Allows configuring voice providers (OpenAI TTS, ElevenLabs, Custom APIs, Edge-TTS), registering keys, and testing speech.
"""

from __future__ import annotations
from typing import Optional, Dict, Any
from cord.tools.base import BaseTool, ToolResult
from cord.voice.tts import tts
from cord.voice.models import OPENAI_VOICES, ELEVENLABS_PRESET_VOICES


class ManageVoiceModelsTool(BaseTool):
    name = "manage_voice"
    description = (
        "Configure, switch, or test voice synthesis models. Supports 'edge' (free built-in), "
        "'openai' (tts-1, tts-1-hd with alloy/nova/echo/etc.), 'elevenlabs' (custom or preset voice IDs), "
        "and 'custom' (OpenAI-compatible audio endpoints). Allows registering API keys and voice IDs."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "set", "test"],
                "description": "'list' to inspect voices, 'set' to update voice settings, 'test' to play sample audio",
            },
            "provider": {
                "type": "string",
                "enum": ["edge", "openai", "elevenlabs", "custom"],
                "description": "Speech synthesis provider",
            },
            "model": {
                "type": "string",
                "description": "Model name (e.g. 'tts-1', 'tts-1-hd', 'eleven_multilingual_v2')",
            },
            "voice_id": {
                "type": "string",
                "description": "Voice identifier (e.g. 'en-US-ChristopherNeural', 'alloy', 'nova', or ElevenLabs voice ID)",
            },
            "api_key": {
                "type": "string",
                "description": "API key for OpenAI or ElevenLabs",
            },
            "base_url": {
                "type": "string",
                "description": "Base URL for custom audio endpoint (e.g. 'http://localhost:8000/v1')",
            },
            "test_phrase": {
                "type": "string",
                "description": "Phrase to speak when action is 'test'",
                "default": "Hello! CORD high-definition voice synthesis is active and operational.",
            },
        },
        "required": ["action"],
    }

    async def execute(
        self,
        action: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        voice_id: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        test_phrase: str = "Hello! CORD voice synthesis is active and operational.",
        **kwargs,
    ) -> ToolResult:
        if action == "list":
            cfg = tts.config
            masked_key = f"{cfg.api_key[:4]}...{cfg.api_key[-4:]}" if cfg.api_key and len(cfg.api_key) > 8 else ("(set)" if cfg.api_key else "(none)")
            lines = [
                "🎙️  CORD Voice Models & TTS Engine Status:",
                f"- Active Provider: [bold cyan]{cfg.provider}[/bold cyan]",
                f"- Active Model: [bold white]{cfg.model}[/bold white]",
                f"- Active Voice ID: [bold yellow]{cfg.voice_id}[/bold yellow]",
                f"- Configured API Key: {masked_key}",
                f"- Custom Base URL: {cfg.base_url or '(default)'}",
                "",
                "Available Providers & Presets:",
                "1. edge: Free built-in neural voices (en-US-ChristopherNeural, en-US-JennyNeural, en-US-GuyNeural, etc.)",
                f"2. openai: tts-1, tts-1-hd (Voices: {', '.join(OPENAI_VOICES)})",
                f"3. elevenlabs: eleven_multilingual_v2 (Presets: {', '.join(ELEVENLABS_PRESET_VOICES.keys())} or custom voice ID)",
                "4. custom: OpenAI-compatible /audio/speech endpoints",
            ]
            return ToolResult(success=True, output="\n".join(lines))

        elif action == "set":
            if not provider:
                return ToolResult(success=False, output="Parameter 'provider' is required to update voice configuration.")
            cfg = tts.configure(
                provider=provider,
                model=model,
                voice_id=voice_id,
                api_key=api_key,
                base_url=base_url,
            )
            return ToolResult(
                success=True,
                output=(
                    f"✔ Voice engine updated successfully!\n"
                    f"- Provider: {cfg.provider}\n"
                    f"- Model: {cfg.model}\n"
                    f"- Voice ID: {cfg.voice_id}"
                ),
            )

        elif action == "test":
            tts.speak(test_phrase, wait=False)
            return ToolResult(
                success=True,
                output=f"Playing sample speech using {tts.config.provider} ({tts.config.voice_id}): '{test_phrase}'",
            )

        return ToolResult(success=False, output=f"Unknown action: '{action}'")
