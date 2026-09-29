"""
CORD Voice - Configurable Voice Models & Audio Providers
Defines voice engine configuration, presets for OpenAI, ElevenLabs, Custom APIs, and Edge-TTS.
"""

from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field, asdict

OPENAI_VOICES = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
ELEVENLABS_PRESET_VOICES = {
    "adam": "pNInz6obpgDQGcFmaJgB",
    "antoni": "ErXwobaYiN019PkySvjV",
    "arnold": "VR6AewLTigWG4xSOukaG",
    "bella": "EXAVITQu4vr4xnSDxMaL",
    "domi": "AZnzlk1XvdvUeBnXmlld",
    "elli": "MF3mGyEYCl7XYWbV9V6O",
    "josh": "TxGEqnHWrfWFTfGW9XjX",
    "rachel": "21m00Tcm4TlvDq8ikWAM",
    "sam": "yoZ06aMxZJJ28mfd3POQ",
}


@dataclass
class VoiceConfig:
    """Configuration for CORD's speech synthesis engine."""
    provider: str = "edge"  # "edge", "openai", "elevenlabs", "custom"
    model: str = "en-US-ChristopherNeural"  # or "tts-1", "tts-1-hd", "eleven_multilingual_v2"
    voice_id: str = "en-US-ChristopherNeural"  # or "alloy", "nova", ElevenLabs voice ID
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    speed: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VoiceConfig":
        return cls(
            provider=data.get("provider", "edge"),
            model=data.get("model", "en-US-ChristopherNeural"),
            voice_id=data.get("voice_id", "en-US-ChristopherNeural"),
            api_key=data.get("api_key"),
            base_url=data.get("base_url"),
            speed=float(data.get("speed", 1.0)),
        )

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "VoiceConfig":
        p = config_path or (Path.home() / ".cord" / "voice.json")
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                return cls.from_dict(data)
            except Exception:
                pass
        return cls()

    def save(self, config_path: Optional[Path] = None) -> None:
        p = config_path or (Path.home() / ".cord" / "voice.json")
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        except Exception:
            pass
