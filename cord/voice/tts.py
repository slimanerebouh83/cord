"""
CORD Voice - Multi-Provider Neural Text-To-Speech (TTS) Engine
Supports Microsoft Edge TTS (free built-in), OpenAI Audio TTS API, ElevenLabs API,
and Custom OpenAI-compatible audio endpoints with instant non-blocking PyGame playback.
"""

from __future__ import annotations
import os
import re
import sys
import tempfile
import asyncio
import subprocess
import threading
import queue
import time
from pathlib import Path
from typing import Optional, Dict, Any

try:
    import edge_tts
    import pygame
    HAS_EDGE_TTS = True
except ImportError:
    HAS_EDGE_TTS = False

from cord.voice.models import VoiceConfig, OPENAI_VOICES, ELEVENLABS_PRESET_VOICES


class TextToSpeech:
    """
    Multi-provider neural speech synthesizer.
    Supports Microsoft Edge TTS, OpenAI TTS, ElevenLabs, and custom endpoints.
    """

    DEFAULT_VOICE = "en-US-ChristopherNeural"

    def __init__(self) -> None:
        self.config = VoiceConfig.load()
        self._queue: queue.Queue[str] = queue.Queue()
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        self._current_process: Optional[subprocess.Popen] = None
        self._enabled: bool = True
        self._is_speaking = False
        self._init_pygame()
        self._start_worker()

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, val: bool) -> None:
        self._enabled = bool(val)

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    def configure(
        self,
        provider: str = "edge",
        model: Optional[str] = None,
        voice_id: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        speed: float = 1.0,
    ) -> VoiceConfig:
        """Updates and persists voice synthesizer configuration."""
        self.config.provider = provider.lower()
        if model:
            self.config.model = model
        if voice_id:
            self.config.voice_id = voice_id
        if api_key is not None:
            self.config.api_key = api_key
        if base_url is not None:
            self.config.base_url = base_url
        self.config.speed = speed
        self.config.save()
        return self.config

    def _init_pygame(self) -> None:
        if HAS_EDGE_TTS:
            try:
                if not pygame.mixer.get_init():
                    pygame.mixer.init()
            except Exception:
                pass

    def _start_worker(self) -> None:
        self._stop_event.clear()
        self._worker_thread = threading.Thread(target=self._run_loop, daemon=True)
        self._worker_thread.start()

    def _clean_text_for_speech(self, text: str) -> str:
        """Strips markdown code fences, symbols, links, and formatting for clean speech."""
        if not text:
            return ""
        cleaned = re.sub(r"```[\s\S]*?```", " Code block executed. ", text)
        cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
        cleaned = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", cleaned)
        cleaned = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", cleaned)
        cleaned = re.sub(r"[*~#><|]", " ", cleaned)
        cleaned = re.sub(r"(?<!\w)_(.*?)(?!\w)_", r"\1", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if len(cleaned) > 600:
            cleaned = cleaned[:600] + "..."
        return cleaned

    def speak(self, text: str, wait: bool = False) -> None:
        """Queues or plays speech aloud."""
        if not self._enabled:
            return
        cleaned = self._clean_text_for_speech(text)
        if not cleaned:
            return

        if wait:
            self._speak_phrase(cleaned)
        else:
            self._queue.put(cleaned)

    def stop(self) -> None:
        """Interrupts and stops speech immediately."""
        try:
            while not self._queue.empty():
                self._queue.get_nowait()
        except Exception:
            pass

        self._stop_event.set()

        if HAS_EDGE_TTS:
            try:
                if pygame.mixer.get_init() and pygame.mixer.music.get_busy():
                    pygame.mixer.music.stop()
                    if hasattr(pygame.mixer.music, "unload"):
                        pygame.mixer.music.unload()
            except Exception:
                pass

        if self._current_process and self._current_process.poll() is None:
            try:
                self._current_process.terminate()
            except Exception:
                pass
            self._current_process = None

        self._stop_event.clear()
        self._is_speaking = False

    def _speak_phrase(self, phrase: str) -> None:
        """Synthesizes and plays a phrase using the configured voice provider."""
        self._is_speaking = True
        try:
            prov = self.config.provider.lower()

            if prov == "openai":
                if self._speak_with_openai(phrase):
                    return

            elif prov == "elevenlabs":
                if self._speak_with_elevenlabs(phrase):
                    return

            elif prov == "custom":
                if self._speak_with_custom(phrase):
                    return

            # Default / Fallback to Edge-TTS
            if HAS_EDGE_TTS:
                if self._speak_with_edge_tts(phrase):
                    return

            # Ultimate offline fallback to local Windows SAPI
            self._speak_with_sapi(phrase)
        finally:
            self._is_speaking = False

    def _play_audio_file(self, temp_file: str) -> bool:
        """Plays an audio file via PyGame with stop event checks."""
        try:
            if self._stop_event.is_set():
                return True
            if not os.path.exists(temp_file) or os.path.getsize(temp_file) == 0:
                return False

            if not pygame.mixer.get_init():
                pygame.mixer.init()

            pygame.mixer.music.load(temp_file)
            pygame.mixer.music.play()

            while pygame.mixer.music.get_busy() and not self._stop_event.is_set():
                time.sleep(0.08)

            pygame.mixer.music.stop()
            if hasattr(pygame.mixer.music, "unload"):
                pygame.mixer.music.unload()
            return True
        except Exception:
            return False

    def _speak_with_edge_tts(self, phrase: str) -> bool:
        """Synthesizes high-fidelity audio using Microsoft Edge TTS."""
        temp_file = None
        try:
            voice = self.config.voice_id if self.config.provider == "edge" else self.DEFAULT_VOICE
            if not voice or "Neural" not in voice:
                voice = self.DEFAULT_VOICE

            fd, temp_file = tempfile.mkstemp(suffix=".mp3")
            os.close(fd)

            async def _synthesize():
                comm = edge_tts.Communicate(phrase, voice=voice, rate="+5%")
                await comm.save(temp_file)

            asyncio.run(_synthesize())
            return self._play_audio_file(temp_file)
        except Exception:
            return False
        finally:
            if temp_file and os.path.exists(temp_file):
                try:
                    import time as _t
                    for _attempt in range(3):
                        try:
                            os.remove(temp_file)
                            break
                        except PermissionError:
                            _t.sleep(0.3)
                except Exception:
                    pass

    def _speak_with_openai(self, phrase: str) -> bool:
        """Synthesizes speech using OpenAI Audio TTS API."""
        api_key = self.config.api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return False

        temp_file = None
        try:
            url = (self.config.base_url or "https://api.openai.com/v1").rstrip("/") + "/audio/speech"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            voice = self.config.voice_id if self.config.voice_id in OPENAI_VOICES else "alloy"
            model = self.config.model if self.config.model.startswith("tts-") else "tts-1"

            payload = {
                "model": model,
                "input": phrase,
                "voice": voice,
                "response_format": "mp3",
                "speed": self.config.speed,
            }

            import httpx
            with httpx.Client(timeout=20.0) as client:
                resp = client.post(url, headers=headers, json=payload)
                if resp.status_code != 200:
                    return False
                audio_bytes = resp.content

            fd, temp_file = tempfile.mkstemp(suffix=".mp3")
            os.write(fd, audio_bytes)
            os.close(fd)

            return self._play_audio_file(temp_file)
        except Exception:
            return False
        finally:
            if temp_file and os.path.exists(temp_file):
                try:
                    import time as _t
                    for _attempt in range(3):
                        try:
                            os.remove(temp_file)
                            break
                        except PermissionError:
                            _t.sleep(0.3)
                except Exception:
                    pass

    def _speak_with_elevenlabs(self, phrase: str) -> bool:
        """Synthesizes speech using ElevenLabs API."""
        api_key = self.config.api_key or os.environ.get("ELEVENLABS_API_KEY")
        if not api_key:
            return False

        temp_file = None
        try:
            voice_id = ELEVENLABS_PRESET_VOICES.get(self.config.voice_id.lower(), self.config.voice_id)
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
            headers = {
                "xi-api-key": api_key,
                "Content-Type": "application/json",
            }
            payload = {
                "text": phrase,
                "model_id": self.config.model if "eleven" in self.config.model else "eleven_multilingual_v2",
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75,
                },
            }

            import httpx
            with httpx.Client(timeout=25.0) as client:
                resp = client.post(url, headers=headers, json=payload)
                if resp.status_code != 200:
                    return False
                audio_bytes = resp.content

            fd, temp_file = tempfile.mkstemp(suffix=".mp3")
            os.write(fd, audio_bytes)
            os.close(fd)

            return self._play_audio_file(temp_file)
        except Exception:
            return False
        finally:
            if temp_file and os.path.exists(temp_file):
                try:
                    import time as _t
                    for _attempt in range(3):
                        try:
                            os.remove(temp_file)
                            break
                        except PermissionError:
                            _t.sleep(0.3)
                except Exception:
                    pass

    def _speak_with_custom(self, phrase: str) -> bool:
        """Synthesizes speech using a custom OpenAI-compatible audio API."""
        if not self.config.base_url:
            return False

        temp_file = None
        try:
            url = self.config.base_url.rstrip("/") + "/audio/speech"
            headers = {"Content-Type": "application/json"}
            if self.config.api_key:
                headers["Authorization"] = f"Bearer {self.config.api_key}"

            payload = {
                "model": self.config.model or "tts-1",
                "input": phrase,
                "voice": self.config.voice_id or "alloy",
                "response_format": "mp3",
                "speed": self.config.speed,
            }

            import httpx
            with httpx.Client(timeout=20.0) as client:
                resp = client.post(url, headers=headers, json=payload)
                if resp.status_code != 200:
                    return False
                audio_bytes = resp.content

            fd, temp_file = tempfile.mkstemp(suffix=".mp3")
            os.write(fd, audio_bytes)
            os.close(fd)

            return self._play_audio_file(temp_file)
        except Exception:
            return False
        finally:
            if temp_file and os.path.exists(temp_file):
                try:
                    import time as _t
                    for _attempt in range(3):
                        try:
                            os.remove(temp_file)
                            break
                        except PermissionError:
                            _t.sleep(0.3)
                except Exception:
                    pass

    def _speak_with_sapi(self, phrase: str) -> None:
        """Fallback offline speech via Windows PowerShell System.Speech."""
        safe_phrase = phrase.replace("'", "''")
        ps_cmd = (
            f"Add-Type -AssemblyName System.Speech; "
            f"$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"$s.Rate = 1; "
            f"$s.Speak('{safe_phrase}')"
        )
        try:
            self._current_process = subprocess.Popen(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._current_process.wait()
        except Exception:
            pass
        finally:
            self._current_process = None

    def _run_loop(self) -> None:
        while True:
            try:
                phrase = self._queue.get(timeout=0.15)
            except queue.Empty:
                continue

            if not self._stop_event.is_set():
                self._speak_phrase(phrase)
            self._queue.task_done()


tts = TextToSpeech()
