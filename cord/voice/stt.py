"""CORD Voice - Speech-To-Text (STT) Engine"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Optional

from cord.core.config import CordConfig

class SpeechToText:
    """Transcribes user speech into text using Whisper API or local audio fallback."""

    def __init__(self, config: Optional[CordConfig] = None) -> None:
        self.config = config

    def transcribe(self, audio_file: Path, config: Optional[CordConfig] = None) -> str:
        """Transcribes the given WAV audio file into text."""
        cfg = config or self.config
        if not audio_file.exists() or audio_file.stat().st_size == 0:
            return ""

        # 1. Check for API key (OpenAI or Groq)
        api_key = (
            (cfg.api_key if cfg else None)
            or os.environ.get("OPENAI_API_KEY")
            or os.environ.get("GROQ_API_KEY")
        )

        base_url = None
        if os.environ.get("GROQ_API_KEY") and not os.environ.get("OPENAI_API_KEY"):
            base_url = "https://api.groq.com/openai/v1"
            model = "whisper-large-v3"
        else:
            model = "whisper-1"

        if api_key:
            try:
                from openai import OpenAI
                client = OpenAI(api_key=api_key, base_url=base_url)
                with open(audio_file, "rb") as f:
                    response = client.audio.transcriptions.create(
                        model=model,
                        file=f,
                    )
                return response.text.strip()
            except Exception as e:
                return f"[Speech transcription error: {e}]"

        return "[Audio recorded: Configure OPENAI_API_KEY or GROQ_API_KEY for Whisper STT]"

stt = SpeechToText()
