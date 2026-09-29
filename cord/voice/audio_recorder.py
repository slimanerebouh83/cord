"""CORD Voice - Native Windows MCI Wave Audio Recorder"""
from __future__ import annotations
import ctypes
import os
import tempfile
import time
from pathlib import Path
from typing import Optional

class AudioRecorder:
    """Records audio from default Windows microphone using native winmm.dll MCI.
    Zero external pip dependencies required.
    """

    def __init__(self) -> None:
        self._recording = False
        self._temp_file: Optional[Path] = None
        self._start_time: float = 0.0
        self.last_error: str = ""

    @property
    def is_recording(self) -> bool:
        return self._recording

    def start(self) -> bool:
        """Starts recording audio from microphone."""
        self.last_error = ""
        if self._recording:
            return True

        if hasattr(ctypes, "windll") and hasattr(ctypes.windll, "winmm"):
            dev_count = ctypes.windll.winmm.waveInGetNumDevs()
            if dev_count == 0:
                self.last_error = "No microphone detected in Windows recording devices. Please plug in or enable a microphone in Windows Sound Settings."
                return False

        temp_dir = Path(tempfile.gettempdir()) / "cord_audio"
        temp_dir.mkdir(parents=True, exist_ok=True)
        self._temp_file = temp_dir / f"rec_{int(time.time() * 1000)}.wav"

        try:
            if hasattr(ctypes, "windll") and hasattr(ctypes.windll, "winmm"):
                # Close any existing alias
                ctypes.windll.winmm.mciSendStringW("close cord_rec", None, 0, 0)
                # Open waveaudio
                res1 = ctypes.windll.winmm.mciSendStringW("open new type waveaudio alias cord_rec", None, 0, 0)
                if res1 != 0:
                    self.last_error = f"Failed to open Windows audio subsystem (MCI error code {res1})."
                    return False

                # Try setting 16-bit 16000Hz (optional optimization, don't fail if unsupported)
                ctypes.windll.winmm.mciSendStringW("set cord_rec bitspersample 16 channels 1 samplespersec 16000", None, 0, 0)

                # Begin recording
                res2 = ctypes.windll.winmm.mciSendStringW("record cord_rec", None, 0, 0)
                if res2 != 0:
                    buf = ctypes.create_unicode_buffer(256)
                    ctypes.windll.winmm.mciGetErrorStringW(res2, buf, 256)
                    self.last_error = buf.value or f"Record failed with error code {res2}."
                    ctypes.windll.winmm.mciSendStringW("close cord_rec", None, 0, 0)
                    return False

                self._recording = True
                self._start_time = time.time()
                return True
        except Exception as e:
            self.last_error = str(e)
            self._recording = False
            return False

        self.last_error = "Windows multimedia API not available."
        return False

    def stop(self) -> Optional[Path]:
        """Stops recording and saves the WAV file."""
        if not self._recording or not self._temp_file:
            return None

        try:
            if hasattr(ctypes, "windll") and hasattr(ctypes.windll, "winmm"):
                ctypes.windll.winmm.mciSendStringW("stop cord_rec", None, 0, 0)
                wav_str = str(self._temp_file.resolve())
                ctypes.windll.winmm.mciSendStringW(f'save cord_rec "{wav_str}"', None, 0, 0)
                ctypes.windll.winmm.mciSendStringW("close cord_rec", None, 0, 0)
                self._recording = False

                if self._temp_file.exists() and self._temp_file.stat().st_size > 100:
                    return self._temp_file
        except Exception:
            pass
        finally:
            self._recording = False

        return None

audio_recorder = AudioRecorder()
